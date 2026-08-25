"""Fortexa training script.

Usage:
  # Generate demo dataset first
  python -m app.ml.synth_data --source ~/faces --out ./data/demo --per-class 200

  # Train
  python -m app.ml.train --data ./data/demo --arch resnet18 --epochs 10
  # (tiny arch for quick smoke tests on CPU)
  python -m app.ml.train --data ./data/demo --arch tiny --epochs 3
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from tqdm import tqdm

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms
    from PIL import Image
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


class ImageFolderDataset(Dataset):
    """Loads images from real/ and fake/ sub-folders. real=0, fake=1."""

    def __init__(self, root: Path, transform=None):
        self.paths = []
        self.labels = []
        self.transform = transform

        for label, cls_name in enumerate(["real", "fake"]):
            cls_dir = root / cls_name
            if not cls_dir.exists():
                continue
            for p in sorted(cls_dir.iterdir()):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    self.paths.append(p)
                    self.labels.append(label)

        if not self.paths:
            raise FileNotFoundError(f"No images in {root}/real/ or {root}/fake/")

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert("RGB")
        label = self.labels[idx]
        if self.transform:
            img = self.transform(img)
        return img, label


def train(args):
    if not _HAS_TORCH:
        raise SystemExit("PyTorch is not installed. Run: pip install -r requirements-ml.txt")

    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    data_dir = Path(args.data)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_size = 224
    train_tf = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(10),
        transforms.ColorJitter(0.1, 0.1, 0.05, 0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    full = ImageFolderDataset(data_dir, transform=train_tf)
    n = len(full)
    n_val = max(1, int(n * 0.15))
    n_train = n - n_val
    train_ds, val_ds = torch.utils.data.random_split(
        full, [n_train, n_val],
        generator=torch.Generator().manual_seed(42),
    )
    val_ds.dataset.transform = val_tf

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0)

    print(f"Train: {n_train} | Val: {n_val} | Arch: {args.arch}")

    from .model import build_model
    model = build_model(args.arch)
    model.to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}")
        for images, labels in pbar:
            images, labels = images.to(device), labels.float().to(device).view(-1, 1)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            preds = (torch.sigmoid(outputs) > 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)
            pbar.set_postfix(loss=loss.item())

        scheduler.step()

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.float().to(device).view(-1, 1)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * images.size(0)
                preds = (torch.sigmoid(outputs) > 0.5).float()
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)

        train_acc = train_correct / train_total
        val_acc = val_correct / val_total
        print(f"  Train loss: {train_loss / train_total:.4f}  acc: {train_acc:.4f} | "
              f"Val loss: {val_loss / val_total:.4f}  acc: {val_acc:.4f}")

        if val_acc > best_acc:
            best_acc = val_acc
            model_path = output_dir / "model.pth"
            torch.save(model.state_dict(), model_path)
            print(f"  ✓ Saved best model to {model_path} (acc: {best_acc:.4f})")

    meta = {
        "arch": args.arch,
        "input_size": input_size,
        "val_acc": round(best_acc, 4),
        "train_samples": n_train,
        "val_samples": n_val,
        "epochs": args.epochs,
        "batch_size": args.batch,
        "lr": args.lr,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = output_dir / "model_meta.json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"Meta saved to {meta_path}")
    print(f"Training complete. Best val acc: {best_acc:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Train Fortexa deepfake detector")
    parser.add_argument("--data", type=str, required=True, help="Dataset root with real/ and fake/")
    parser.add_argument("--arch", type=str, default="resnet18", choices=("tiny", "resnet18", "efficientnet_b0"))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--out", type=str, default="./runs")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()