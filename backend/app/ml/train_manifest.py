"""Training on source-disjoint manifests; no test data is used for model selection."""
import argparse
import hashlib
import json
import random
import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from PIL import Image


class RandomJPEG:
    """Compression augmentation applied equally to both classes."""
    def __call__(self, image):
        if random.random() < .5:
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=random.randint(60, 95))
            buffer.seek(0)
            with Image.open(buffer) as compressed:
                return compressed.convert("RGB")
        return image


class ManifestDataset(Dataset):
    def __init__(self, root, records, transform):
        self.root, self.records, self.transform = root, records, transform
    def __len__(self):
        return len(self.records)
    def __getitem__(self, i):
        row = self.records[i]
        with Image.open(self.root / row["path"]) as image:
            image = image.convert("RGB")
        return self.transform(image), row["label"]


def load_manifest(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    groups, hashes = {}, {}
    counts = {s: [0, 0] for s in ("train", "val", "test")}
    for row in manifest["records"]:
        split, group, label = row["split"], str(row["group"]), row["label"]
        if split not in counts or label not in (0, 1) or not group:
            raise ValueError("Invalid split/group/label")
        image_path = (path.parent / row["path"]).resolve()
        if not image_path.is_relative_to(path.parent):
            raise ValueError("Image path escapes dataset root")
        if group in groups and groups[group] != split:
            raise ValueError(f"Source-group leakage: {group}")
        groups[group] = split
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            digest = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        if digest in hashes:
            prior_split, prior_label = hashes[digest]
            if prior_split != split:
                raise ValueError("Identical decoded images occur across splits")
            if prior_label != label:
                raise ValueError("Identical image has conflicting labels")
        hashes[digest] = (split, label)
        counts[split][label] += 1
    if any(min(value) < 2 for value in counts.values()):
        raise ValueError(f"Each split needs at least two samples per class: {counts}")
    return manifest, path.parent, counts


def metrics(labels, scores):
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score, confusion_matrix
    labels, scores = np.asarray(labels), np.asarray(scores)
    predicted = scores >= .5
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predicted, average="binary", zero_division=0)
    decisive = (scores <= .4) | (scores >= .6)
    return {"samples": len(labels), "accuracy": float(accuracy_score(labels, predicted)),
            "precision": float(precision), "recall": float(recall), "f1": float(f1),
            "roc_auc": float(roc_auc_score(labels, scores)),
            "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1]).tolist(),
            "decisive_coverage": float(decisive.mean()),
            "decisive_accuracy": float((predicted[decisive] == labels[decisive]).mean()) if decisive.any() else None}


def evaluate(model, loader, device):
    model.eval()
    labels, scores = [], []
    with torch.inference_mode():
        for images, targets in loader:
            scores.extend(torch.sigmoid(model(images.to(device))).flatten().cpu().tolist())
            labels.extend(targets.tolist())
    return metrics(labels, scores)


def train(args):
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(args.threads)
    manifest, root, counts = load_manifest(args.manifest)
    if not manifest.get("genuine_manipulated_media") and not args.allow_demo:
        raise ValueError("Supply a sourced genuine-data manifest. Demo data is only allowed for smoke tests.")
    if manifest.get("genuine_manipulated_media") and not manifest.get("preprocessing", "").startswith("Haar-detected largest face"):
        raise ValueError("Genuine-data training requires face crops matching the inference pipeline")
    out = Path(args.out)
    if (out / "model.pth").exists():
        raise ValueError("Use a new output directory; existing checkpoints are preserved.")
    out.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    normal = [transforms.ToTensor(), transforms.Normalize([.485, .456, .406], [.229, .224, .225])]
    train_tf = transforms.Compose([transforms.Resize((224, 224)), transforms.RandomHorizontalFlip(),
                                   transforms.RandomRotation(5), transforms.ColorJitter(.08, .08, .05, .02), RandomJPEG(), *normal])
    val_tf = transforms.Compose([transforms.Resize((224, 224)), *normal])
    datasets = {s: ManifestDataset(root, [r for r in manifest["records"] if r["split"] == s],
                                  train_tf if s == "train" else val_tf) for s in counts}
    loaders = {s: DataLoader(ds, batch_size=args.batch, shuffle=s == "train", num_workers=0) for s, ds in datasets.items()}
    from .model import build_model
    initial_weights = getattr(args, "init_weights", None)
    train_last_block = getattr(args, "train_last_block", False)
    model = build_model(args.arch, pretrained=not args.no_pretrained and not initial_weights).to(device)
    if initial_weights:
        model.load_state_dict(torch.load(initial_weights, map_location=device, weights_only=True))
    if train_last_block:
        if args.arch != "resnet18" or args.freeze_backbone:
            raise ValueError("Last-block fine-tuning requires resnet18 without --freeze-backbone")
        for name, parameter in model.named_parameters():
            parameter.requires_grad = name.startswith(("layer4.", "fc."))
    if args.freeze_backbone and args.arch != "tiny":
        for name, parameter in model.named_parameters():
            parameter.requires_grad = name.startswith("fc.") or name.startswith("classifier.")
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([counts["train"][0] / counts["train"][1]], device=device))
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=1e-4)
    best_auc, selected_epoch, history = -1, 0, []
    if initial_weights:
        baseline_validation = evaluate(model, loaders["val"], device)
        best_auc = baseline_validation["roc_auc"]
        history.append({"epoch": 0, "train_loss": None, "validation": baseline_validation})
        torch.save(model.state_dict(), out / "model.pth")
        print("INITIAL_VALIDATION " + json.dumps(baseline_validation), flush=True)
    print(json.dumps({"device": device, "splits": counts, "source": manifest["source"]}), flush=True)
    for epoch in range(args.epochs):
        model.train()
        if args.freeze_backbone or train_last_block:
            for module in model.modules():
                if isinstance(module, nn.BatchNorm2d):
                    module.eval()
        total_loss = 0
        for images, labels in loaders["train"]:
            optimizer.zero_grad()
            loss = criterion(model(images.to(device)).view(-1), labels.float().to(device))
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(labels)
        validation = evaluate(model, loaders["val"], device)
        row = {"epoch": epoch + 1, "train_loss": total_loss / len(datasets["train"]), "validation": validation}
        history.append(row)
        print(json.dumps(row), flush=True)
        if validation["roc_auc"] > best_auc:
            best_auc = validation["roc_auc"]
            selected_epoch = epoch + 1
            torch.save(model.state_dict(), out / "model.pth")
        (out / "training_progress.json").write_text(json.dumps({"history": history,
            "selected_epoch": selected_epoch, "selection_metric": "validation_roc_auc",
            "complete": False}, indent=2), encoding="utf-8")
    model.load_state_dict(torch.load(out / "model.pth", map_location=device, weights_only=True))
    test = evaluate(model, loaders["test"], device)
    selected_validation = evaluate(model, loaders["val"], device)
    genuine = bool(manifest.get("genuine_manipulated_media"))
    meta = {"arch": args.arch, "input_size": 224, "epochs": args.epochs, "batch_size": args.batch,
            "lr": args.lr, "selected_epoch": selected_epoch, "selection_metric": "validation_roc_auc",
            "freeze_backbone": args.freeze_backbone, "pretrained_initialization": not args.no_pretrained and not initial_weights and args.arch != "tiny",
            "train_last_block": train_last_block,
            "initial_checkpoint_sha256": hashlib.sha256(Path(initial_weights).read_bytes()).hexdigest() if initial_weights else None,
            "initial_checkpoint": str(initial_weights) if initial_weights else None,
            "device": device, "split_counts": counts,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset_source": manifest["source"], "manifest_sha256": hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
            "train_samples": len(datasets["train"]), "val_samples": len(datasets["val"]),
            "test_samples": len(datasets["test"]), "val_acc": selected_validation["accuracy"],
            "validation_metrics": selected_validation,
            "independent_evaluation": genuine, "calibrated": False, "preprocessing": "face_crop_margin_0.2",
            "evaluation_scope": "source-group-disjoint held-out images; not a cross-dataset or video benchmark" if genuine else "synthetic smoke test only",
            "test_metrics": test}
    (out / "model_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out / "evaluation.json").write_text(json.dumps({"metadata": meta, "history": history, "test": test}, indent=2), encoding="utf-8")
    (out / "training_progress.json").write_text(json.dumps({"history": history,
        "selected_epoch": selected_epoch, "selection_metric": "validation_roc_auc",
        "complete": True}, indent=2), encoding="utf-8")
    print("HELD_OUT_TEST " + json.dumps(test), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--arch", choices=["tiny", "resnet18", "efficientnet_b0"], default="resnet18")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--freeze-backbone", action="store_true")
    parser.add_argument("--train-last-block", action="store_true", help="Train only ResNet18 layer4 and classifier; keep batch-normalization statistics fixed")
    parser.add_argument("--init-weights", help="Initialize from a compatible checkpoint; baseline is retained unless validation AUC improves")
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--allow-demo", action="store_true")
    args = parser.parse_args()
    if min(args.epochs, args.batch, args.threads) < 1:
        parser.error("epochs, batch and threads must be positive")
    train(args)


if __name__ == "__main__":
    main()
