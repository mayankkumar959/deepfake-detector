"""Train a new AI-image head on full-image, source-group-disjoint real/AI data.

Frozen SigLIP encoder, JPEG augmentation for BOTH labels, val-only C selection.
This small run is a prototype, not all-generator/real-world accuracy certification.
"""
import hashlib
import json
from pathlib import Path
import random
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import requests
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix, precision_recall_fscore_support
from transformers import AutoImageProcessor, SiglipForImageClassification

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/general-ai-training-indoor'
BASE = ROOT / 'runs/general-ai-siglip'
OUT = ROOT / 'runs/general-ai-trained-indoor-20261005'
SOURCES = [(0, 'Multimodal-Fatima/Imagenette_validation', 'validation'),
           (0, 'detection-datasets/coco', 'val'), (0, 'aradhye/nyu_depth_v2', 'train'),
           (1, 'svjack/diffusiondb_random_10k', 'train')]


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def prepare():
    manifest_path = DATA / 'manifest.json'
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    DATA.mkdir(parents=True, exist_ok=True)
    jobs = []
    for label, dataset, split in SOURCES:
        response = requests.get('https://datasets-server.huggingface.co/first-rows',
                                params={'dataset': dataset, 'config': 'default', 'split': split}, timeout=60)
        response.raise_for_status()
        rows = response.json()['rows']
        for item in rows[5:100]:  # First five samples were diagnostic fixtures; not used to train/select.
            row, index = item['row'], item['row_idx']
            identity = str(row.get('prompt') or row.get('id') or row.get('image_id') or index).strip().lower()
            group = hashlib.sha256((dataset + ':' + identity).encode()).hexdigest()
            if dataset == 'aradhye/nyu_depth_v2':
                group = 'nyu-indoor-training-only-stream'  # No scene IDs: never claim independent room holdout.
            jobs.append((label, dataset, index, group, row['image']['src']))
    def download(job):
        label, source, index, group, url = job
        relative = f'{label}-{hashlib.sha256(source.encode()).hexdigest()[:8]}-{index}.jpg'
        path = DATA / relative
        previous = ROOT / 'data/general-ai-training-scenes' / relative
        if not path.exists() and previous.exists():
            path.write_bytes(previous.read_bytes())
        if not path.exists():
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            path.write_bytes(response.content)
        image = cv2.imread(str(path))
        if image is None or min(image.shape[:2]) < 128 or float(image.std()) < 2:
            return None
        pixel_hash = hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()
        return {'path': relative, 'label': label, 'group': group, 'source': source, 'source_row': index,
                'sha256': digest(path), 'pixel_sha256': pixel_hash}
    with ThreadPoolExecutor(max_workers=4) as workers:
        rows = [row for row in workers.map(download, jobs) if row]
    # Reject/remove repeated decoded pixels before splitting, with no label conflicts.
    seen, unique = {}, []
    for row in rows:
        if row['pixel_sha256'] in seen:
            if seen[row['pixel_sha256']] != row['label']:
                raise ValueError('Conflicting image labels')
            continue
        seen[row['pixel_sha256']] = row['label']
        unique.append(row)
    rng = random.Random(42)
    for label in (0, 1):
        groups = sorted({row['group'] for row in unique if row['label'] == label})
        rng.shuffle(groups)
        count = len(groups)
        group_splits = {group: 'train' if i < int(.7 * count) else 'val' if i < int(.85 * count) else 'test' for i, group in enumerate(groups)}
        for row in unique:
            if row['label'] == label:
                row['split'] = 'train' if row['source'] == 'aradhye/nyu_depth_v2' else group_splits[row['group']]
    manifest = {'task': 'AI-generated vs real; compression preserves labels', 'records': unique,
                'limitations': 'Small single-generator dataset; real mirror/AI mirror source separation may introduce dataset bias. Not a representative benchmark.',
                'diagnostic_fixture_rows_excluded': [0, 1, 2, 3, 4]}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def metrics(labels, scores):
    predicted = np.asarray(scores) >= .5
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predicted, average='binary', zero_division=0)
    return {'samples': len(labels), 'accuracy': float(accuracy_score(labels, predicted)), 'roc_auc': float(roc_auc_score(labels, scores)),
            'precision': float(precision), 'recall': float(recall), 'f1': float(f1), 'confusion_matrix': confusion_matrix(labels, predicted).tolist()}


def train():
    if OUT.exists():
        raise ValueError('Output candidate already exists; refusing to overwrite a training run')
    manifest = prepare()
    rows = manifest['records']
    groups = {}
    for row in rows:
        if row['group'] in groups and groups[row['group']] != row['split']:
            raise ValueError('Source-group leakage')
        groups[row['group']] = row['split']
    counts = {split: [sum(row['split'] == split and row['label'] == label for row in rows) for label in (0, 1)] for split in ('train', 'val', 'test')}
    if any(min(count) < 5 for count in counts.values()):
        raise ValueError(f'Insufficient data: {counts}')
    print(json.dumps({'source_group_split_counts': counts}), flush=True)
    torch.set_num_threads(2)
    model = SiglipForImageClassification.from_pretrained(str(BASE), local_files_only=True, use_safetensors=True).eval()
    processor = AutoImageProcessor.from_pretrained(str(BASE), local_files_only=True, use_fast=False)
    features = {split: [] for split in counts}
    labels = {split: [] for split in counts}
    start = time.time()
    with torch.inference_mode():
        for index, row in enumerate(rows):
            image = cv2.imread(str(DATA / row['path']))
            for quality in ((95, 60) if row['split'] == 'train' else (85,)):
                _, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                rgb = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
                inputs = processor(images=Image.fromarray(rgb), return_tensors='pt')
                output = model.vision_model(pixel_values=inputs['pixel_values']).last_hidden_state.mean(dim=1)[0].numpy()
                features[row['split']].append(output)
                labels[row['split']].append(row['label'])
            if index % 10 == 0:
                print(json.dumps({'feature_progress': index + 1, 'images': len(rows), 'seconds': round(time.time() - start, 1)}), flush=True)
    scaler = StandardScaler().fit(features['train'])
    x_train, x_val = scaler.transform(features['train']), scaler.transform(features['val'])
    best = None
    trials = []
    for c_value in (.001, .01, .1, 1., 10.):
        classifier = LogisticRegression(C=c_value, max_iter=2000, class_weight='balanced', random_state=42).fit(x_train, labels['train'])
        validation = metrics(labels['val'], classifier.predict_proba(x_val)[:, 1])
        trials.append({'C': c_value, 'validation': validation})
        if best is None or validation['roc_auc'] > best[0]:
            best = (validation['roc_auc'], classifier, c_value, validation)
    classifier = best[1]
    # Fold train-only scaler into binary AI logit; class 0=AI, class 1=human.
    weight = classifier.coef_[0] / scaler.scale_
    bias = classifier.intercept_[0] - np.dot(weight, scaler.mean_)
    with torch.no_grad():
        model.classifier.weight.zero_()
        model.classifier.bias.zero_()
        model.classifier.weight[0].copy_(torch.tensor(weight, dtype=torch.float32))
        model.classifier.bias[0] = float(bias)
    scores = classifier.predict_proba(scaler.transform(features['test']))[:, 1]
    heldout = metrics(labels['test'], scores)  # Only now view test results, after val selection.
    OUT.mkdir()
    model.save_pretrained(str(OUT), safe_serialization=True)
    processor.save_pretrained(str(OUT))
    evaluation = {'selection': 'validation ROC-AUC only; lowest C retained on ties', 'split_counts': counts,
                  'validation_trials': trials, 'selected_C': best[2], 'validation': best[3], 'test': heldout,
                  'limitations': manifest['limitations']}
    (OUT / 'evaluation.json').write_text(json.dumps(evaluation, indent=2))
    metadata = {'source': 'https://huggingface.co/Ateeqq/ai-vs-human-image-detector',
                'source_revision': '60e82406916921b823616bee33397baab38af3f0', 'task': manifest['task'],
                'training': 'Locally trained new binary head, frozen SigLIP encoder, both-class JPEG augmentation',
                'manifest_sha256': digest(DATA / 'manifest.json'), 'calibrated': False, 'evaluation_scope': manifest['limitations'],
                'selected_C': best[2], 'test_metrics': heldout, 'split_counts': counts,
                'sha256': {name: digest(OUT / name) for name in ('model.safetensors', 'config.json', 'preprocessor_config.json')}}
    (OUT / 'model_meta.json').write_text(json.dumps(metadata, indent=2))
    print('NEW_HEAD_EVALUATION ' + json.dumps(evaluation), flush=True)


if __name__ == '__main__':
    train()
