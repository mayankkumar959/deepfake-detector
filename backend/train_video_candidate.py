"""Local research candidate only: frozen SigLIP + video-level temporal statistics.

Downloads a bounded, revision-pinned academic ComGenVid subset. Never changes
the production model/config. Scores are uncalibrated, not forensic proof.
Usage: python train_video_candidate.py [--prepare-only | --predict FILE]
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import threading
import time
from urllib.parse import quote

import cv2
import joblib
import numpy as np
from PIL import Image
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch
from transformers import AutoImageProcessor, SiglipForImageClassification

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/video-training-comgenvid-20261006'
OUT = ROOT / 'runs/candidate-video-comgenvid-20261006'
BASE = ROOT / 'runs/general-ai-siglip'
REPO = 'OmerXYZ/comgenvid'
REVISION = 'c5093999e799c897c977a8699da95ebbc59cc9cb'
SEED = 20261006
FRAME_COUNT = 6
MAX_FILE = 12 * 1024 * 1024
MAX_DATA = 1024 * 1024 * 1024
EXTRA_MANIFESTS = []


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def sha(path):
    if path.is_dir():
        digest = hashlib.sha256()
        for item in sorted(path.glob('*.jpg')):
            digest.update(item.name.encode())
            digest.update(item.read_bytes())
        return digest.hexdigest()
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_group(row):
    stem = Path(row['file_name']).stem
    # All clips from the same YouTube recording / Sora creator stay together.
    # VEO3 upstream prompt relationships are unavailable: only filename-level
    # separation is possible, so this is NOT a prompt-disjoint evaluation.
    identity = stem.rsplit('_', 2)[0] if row['source_model'] == 'MSVD' else stem.split('_')[0]
    return row['source_model'] + ':' + identity


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = DATA / 'manifest.json'
    if manifest.exists():
        rows = json.loads(manifest.read_text(encoding='utf-8'))
        for row in rows:
            if sha(DATA / row['path']) != row['sha256']:
                raise ValueError('Dataset file changed: ' + row['path'])
        return rows
    if shutil.disk_usage(DATA).free < 2 * MAX_DATA:
        raise RuntimeError('Need at least 2 GiB free disk space')
    base = f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/'
    response = requests.get(base + 'metadata.jsonl', timeout=60)
    response.raise_for_status()
    metadata = [json.loads(line) for line in response.text.splitlines() if line]
    card = requests.get(base + 'README.md', timeout=60)
    card.raise_for_status()
    (DATA / 'SOURCE_README.md').write_text(card.text, encoding='utf-8')
    credits = requests.get(base + 'sora_sampled_videos.csv', timeout=60)
    credits.raise_for_status()
    (DATA / 'SORA_CREATOR_CREDITS.csv').write_text(credits.text, encoding='utf-8')
    groups = defaultdict(list)
    for row in metadata:
        if row['source_model'] in {'MSVD', 'Sora', 'VEO3'} and min(row['width'], row['height']) >= 224:
            groups[row['source_model']].append(row)
    rng = random.Random(SEED)
    jobs = []
    for source, limit in [('MSVD', 96), ('Sora', 48), ('VEO3', 48)]:
        candidates = groups[source]
        rng.shuffle(candidates)
        unique = {}
        for row in candidates:
            unique.setdefault(source_group(row), row)
        selected = list(unique.values())[:limit]
        if len(selected) != limit:
            raise ValueError('Insufficient unique recording/creator groups: ' + source)
        for index, row in enumerate(selected):
            split = 'test' if index < round(limit * .2) else 'val' if index < round(limit * .4) else 'train'
            jobs.append({**row, 'split': split, 'label': int(source != 'MSVD'), 'group': source_group(row)})

    budget_lock = threading.Lock()
    used_bytes = sum(p.stat().st_size for p in DATA.glob('*.mp4'))

    def download(row):
        nonlocal used_bytes
        relative = hashlib.sha256(row['file_name'].encode()).hexdigest()[:24] + '.mp4'
        target = DATA / relative
        if not target.exists():
            url = base + quote(row['file_name'], safe='/')
            try:
                with requests.get(url, stream=True, timeout=(20, 90)) as res:
                    res.raise_for_status()
                    if int(res.headers.get('Content-Length', '0')) > MAX_FILE:
                        return None
                    content = bytearray()
                    for chunk in res.iter_content(256 * 1024):
                        content.extend(chunk)
                        if len(content) > MAX_FILE:
                            return None
                    with budget_lock:
                        if used_bytes + len(content) > MAX_DATA:
                            return None
                        target.write_bytes(content)
                        used_bytes += len(content)
            except requests.RequestException as exc:
                print('download skipped', row['source_model'], type(exc).__name__, flush=True)
                return None
        cap = cv2.VideoCapture(str(target))
        ok, _ = cap.read()
        cap.release()
        if not ok:
            return None
        return {k: row[k] for k in ('file_name', 'source_model', 'split', 'label', 'group')} | {
            'path': relative, 'sha256': sha(target), 'bytes': target.stat().st_size,
            'repository': REPO, 'revision': REVISION}

    rows = []
    with ThreadPoolExecutor(max_workers=3) as workers:
        for i, row in enumerate(workers.map(download, jobs)):
            if row:
                rows.append(row)
            if (i + 1) % 12 == 0:
                print('download', i + 1, '/', len(jobs), 'accepted', len(rows), flush=True)
    # Exact-file duplicates are never allowed across splits (or labels).
    unique = {}
    for row in rows:
        previous = unique.get(row['sha256'])
        if previous and previous['label'] != row['label']:
            raise ValueError('Conflicting duplicate video labels')
        unique.setdefault(row['sha256'], row)
    rows = list(unique.values())
    if sum(row['bytes'] for row in rows) > MAX_DATA:
        raise RuntimeError('Selected dataset exceeded 1 GiB; do not train')
    for split in ('train', 'val', 'test'):
        if any(sum(r['split'] == split and r['label'] == label for r in rows) < 8 for label in (0, 1)):
            raise ValueError('Insufficient videos for an honest split: ' + split)
    save_json(manifest, rows)
    print('prepared', len(rows), 'videos;', round(sum(r['bytes'] for r in rows) / 2**20, 1), 'MiB', flush=True)
    return rows


def frames(path, compressed=False):
    if Path(path).is_dir():
        paths = sorted(Path(path).glob('*.jpg'))
        if len(paths) != FRAME_COUNT:
            raise ValueError('Expected exactly six source video frames')
        output = []
        for item in paths:
            image = Image.open(item).convert('RGB').resize((224, 224))
            if compressed:
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=55)
                buffer.seek(0)
                image = Image.open(buffer).convert('RGB')
            output.append(image)
        return output
    cap = cv2.VideoCapture(str(path))
    try:
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count < FRAME_COUNT:
            raise ValueError('Too few readable video frames')
        output = []
        for index in np.linspace(0, count - 1, FRAME_COUNT).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = cap.read()
            if not ok:
                raise ValueError('Could not decode sampled frame')
            # Every source receives the same spatial processing; no metadata,
            # codec, filename, duration or source ID is fed to the classifier.
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((224, 224))
            if compressed:
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=55)
                buffer.seek(0)
                image = Image.open(buffer).convert('RGB')
            output.append(image)
        return output
    finally:
        cap.release()


def aggregate(sequence):
    delta = np.diff(sequence, axis=0)
    return np.concatenate([sequence.mean(axis=0), sequence.std(axis=0), np.abs(delta).mean(axis=0)]).astype(np.float32)


def require_visual_information(images):
    if sum(float(np.asarray(image.convert('L')).std()) >= 2 for image in images) < 3:
        raise ValueError('Insufficient visual detail in sampled video frames')


def load_encoder():
    torch.set_num_threads(2)
    model = SiglipForImageClassification.from_pretrained(BASE, local_files_only=True, use_safetensors=True).eval()
    processor = AutoImageProcessor.from_pretrained(BASE, local_files_only=True, use_fast=False)
    return model, processor


def feature(path, model, processor, compressed=False):
    sequence = []
    images = frames(path, compressed)
    require_visual_information(images)
    with torch.inference_mode():
        for image in images:
            inputs = processor(images=image, return_tensors='pt')
            sequence.append(model.vision_model(pixel_values=inputs['pixel_values']).last_hidden_state.mean(dim=1)[0].numpy())
    return aggregate(np.stack(sequence))


def metrics(labels, probabilities):
    predictions = probabilities >= .5
    accuracy = float(accuracy_score(labels, predictions))
    n, z = len(labels), 1.96
    center = (accuracy + z*z/(2*n)) / (1 + z*z/n)
    margin = z * np.sqrt(accuracy*(1-accuracy)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return {'videos': len(labels), 'accuracy': float(accuracy_score(labels, predictions)),
            'accuracy_wilson_95_interval': [float(center-margin), float(center+margin)],
            'balanced_accuracy': float(balanced_accuracy_score(labels, predictions)) if len(set(labels)) == 2 else None,
            'roc_auc': float(roc_auc_score(labels, probabilities)) if len(set(labels)) == 2 else None,
            'confusion_matrix_real_fake': confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
            'inconclusive_0.4_to_0.6': int(((probabilities > .4) & (probabilities < .6)).sum()),
            'decision_counts_0.4_0.6': {'real': int((probabilities <= .4).sum()),
                                       'fake': int((probabilities >= .6).sum())},
            'false_fake_decisions': int(((labels == 0) & (probabilities >= .6)).sum()),
            'false_real_decisions': int(((labels == 1) & (probabilities <= .4)).sum())}


def domain(row):
    if row['source_model'] in ('VidTIMIT', 'DeepfakeTIMIT-HQ'):
        return 'face-swap'
    if row['source_model'] in ('HDTF', 'X-Dub'):
        return 'lip-sync'
    return 'generated-video'


def domain_label_weights(rows):
    counts = Counter((domain(row), row['label']) for row in rows)
    return np.array([len(rows) / (len(counts) * counts[domain(row), row['label']]) for row in rows])


def train():
    rows = prepare()
    for manifest in EXTRA_MANIFESTS:
        additional = json.loads(manifest.read_text(encoding='utf-8'))
        for row in additional:
            if sha(Path(row['path'])) != row['sha256']:
                raise ValueError('Additional video data changed: ' + row['path'])
        rows.extend(additional)
    if len({r['sha256'] for r in rows}) != len(rows):
        raise ValueError('Duplicate files across combined datasets; split audit required')
    OUT.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    manifest_stamp = OUT / 'feature_manifest.json'
    stamp = {'manifest_sha256': fingerprint, 'encoder_sha256': sha(BASE / 'model.safetensors'),
             'preprocessor_sha256': sha(BASE / 'preprocessor_config.json'),
             'encoder_config_sha256': sha(BASE / 'config.json'),
             'frames': FRAME_COUNT, 'features': 'mean,std,mean_absolute_temporal_difference', 'jpeg_quality': 55}
    if manifest_stamp.exists() and json.loads(manifest_stamp.read_text()) != stamp:
        raise ValueError('Feature configuration changed: choose a new candidate directory')
    save_json(manifest_stamp, stamp)
    model, processor = load_encoder()
    clean, degraded = [], []
    start = time.monotonic()
    for index, row in enumerate(rows):
        cache = OUT / (Path(row['path']).stem + '.npz')
        prior_cache = ROOT / 'runs/candidate-video-comgenvid-20261006' / cache.name
        prior_stamp = prior_cache.parent / 'feature_manifest.json'
        if not cache.exists() and prior_cache.exists() and prior_stamp.exists():
            prior = json.loads(prior_stamp.read_text())
            if all(prior.get(k) == stamp[k] for k in stamp if k != 'manifest_sha256'):
                shutil.copyfile(prior_cache, cache)
        if cache.exists():
            with np.load(cache) as item:
                a, b = item['clean'], item['jpeg']
        else:
            a = feature(DATA / row['path'], model, processor)
            b = feature(DATA / row['path'], model, processor, True)
            pending = cache.with_suffix('.partial.npz')
            np.savez_compressed(pending, clean=a, jpeg=b)
            pending.replace(cache)
        clean.append(a)
        degraded.append(b)
        print('features', index + 1, '/', len(rows), 'elapsed_s', round(time.monotonic() - start), flush=True)
    clean, degraded = np.stack(clean), np.stack(degraded)
    if not np.isfinite(clean).all() or not np.isfinite(degraded).all():
        raise ValueError('Non-finite video features')
    labels = np.array([r['label'] for r in rows])
    indices = {split: np.array([i for i, r in enumerate(rows) if r['split'] == split]) for split in ('train', 'val', 'test')}
    for left, right in (('train', 'val'), ('train', 'test'), ('val', 'test')):
        assert not {rows[i]['group'] for i in indices[left]} & {rows[i]['group'] for i in indices[right]}
    fit = indices['train']
    domains = np.array([domain(row) for row in rows])
    weights = domain_label_weights([rows[i] for i in fit])
    best = None
    trials = []
    for c in (.001, .01, .1, 1):
        classifier = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1500, random_state=SEED))
        classifier.fit(np.concatenate([clean[fit], degraded[fit]]), np.tile(labels[fit], 2),
                       logisticregression__sample_weight=np.tile(weights, 2))
        val = indices['val']
        predictions = classifier.predict(np.concatenate([clean[val], degraded[val]]))
        val_labels, val_domains = np.tile(labels[val], 2), np.tile(domains[val], 2)
        domain_scores = {d: float(balanced_accuracy_score(val_labels[val_domains == d], predictions[val_domains == d]))
                         for d in sorted(set(val_domains))}
        score = float(np.mean(list(domain_scores.values())))
        trials.append({'C': c, 'validation_macro_domain_balanced_accuracy': score, 'domain_scores': domain_scores})
        if best is None or score > best[0]:
            best = score, classifier, c
    classifier = best[1]
    test = indices['test']
    probabilities = classifier.predict_proba(clean[test])[:, 1]
    jpeg_probabilities = classifier.predict_proba(degraded[test])[:, 1]
    report = {'status': 'experimental_not_production', 'repository': REPO, 'revision': REVISION,
              'seed': SEED, 'features': stamp, 'selected_C': best[2], 'validation_trials': trials,
              'training_weighting': 'Equal domain/label mass; scaler train-only; C selected on macro-domain validation balanced accuracy.',
              'binary_metrics_threshold': .5, 'decision_thresholds': {'real_max': .4, 'fake_min': .6},
              'preprocessor_sha256': sha(BASE / 'preprocessor_config.json'),
              'split_counts': {s: dict(Counter(rows[i]['source_model'] for i in ids)) for s, ids in indices.items()},
              'test': metrics(labels[test], probabilities), 'jpeg_frame_stress_test': metrics(labels[test], jpeg_probabilities),
              'limitations': ['Only MSVD real / Sora / VEO3 generated video data.',
                  'Face-swap/lip-sync coverage is limited to sources actually listed in split_counts; not certified.',
                  'Visual-only, six sampled frames; no audio/video synchronisation assessment.',
                  'Source/generator/codec shortcuts remain possible despite identical frame preprocessing.',
                  'Visible watermarks/source signatures and differing sampled clip durations may introduce shortcuts.',
                  'Recording/creator-group disjoint; prompt/semantic relationships across generators unavailable.',
                  'Cross-dataset person/scene overlap cannot be fully audited from the available metadata.',
                  'JPEG frame degradation is NOT a WhatsApp/H.264 video-compression validation.',
                  'Small held-out benchmark; not all-generator, all-real-world accuracy.',
                  'Scores are uncalibrated classifier support, not authenticity probabilities.'],
              'test_predictions': [{'path': rows[i]['path'], 'source': rows[i]['source_model'], 'label': int(labels[i]),
                                    'ai_support': float(p), 'jpeg_ai_support': float(q)} for i, p, q in zip(test, probabilities, jpeg_probabilities)]}
    report['limitations'][0] = 'Small selected video dataset; see split_counts for actual trained sources.'
    if EXTRA_MANIFESTS:
        report['limitations'].append('Lip-sync original/fake clips are speaker-matched, not identical source segments; source shortcuts remain possible.')
        report['limitations'].append('Face-swap data represents an older single generator, not all modern swaps.')
    report['dataset_sources'] = sorted({(r.get('repository', REPO), r.get('revision', 'publisher-record')) for r in rows})
    for source in sorted({rows[i]['source_model'] for i in test}):
        mask = np.array([rows[i]['source_model'] == source for i in test])
        report.setdefault('per_source_test', {})[source] = metrics(labels[test][mask], probabilities[mask])
    pending_head = OUT / 'video_head.partial.joblib'
    joblib.dump(classifier, pending_head)
    pending_head.replace(OUT / 'video_head.joblib')
    report['head_sha256'] = sha(OUT / 'video_head.joblib')
    save_json(OUT / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'split_counts', 'test', 'jpeg_frame_stress_test', 'per_source_test')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--predict', type=Path)
    parser.add_argument('--extra-manifest', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    EXTRA_MANIFESTS = args.extra_manifest
    mixed = ROOT / 'runs/candidate-video-mixed-20261006'
    if args.predict and not args.output and (mixed / 'report.json').exists():
        OUT = mixed
    if args.output:
        OUT = args.output.resolve()
        if OUT.parent != (ROOT / 'runs').resolve() or not OUT.name.startswith('candidate-'):
            raise ValueError('Output must be a local ignored runs/candidate-* directory')
    if args.predict:
        if not args.predict.exists():
            parser.error('Video file not found')
        try:
            require_visual_information(frames(args.predict))
        except ValueError as exc:
            print(json.dumps({'status': 'experimental', 'decision': 'inconclusive', 'reason': str(exc)}))
            raise SystemExit(0)
        metadata = json.loads((OUT / 'report.json').read_text())
        stamp = json.loads((OUT / 'feature_manifest.json').read_text())
        if stamp['encoder_sha256'] != sha(BASE / 'model.safetensors') or stamp['frames'] != FRAME_COUNT:
            raise ValueError('Candidate encoder/frame configuration mismatch')
        if metadata.get('preprocessor_sha256') != sha(BASE / 'preprocessor_config.json'):
            raise ValueError('Candidate preprocessor mismatch')
        if stamp.get('encoder_config_sha256') != sha(BASE / 'config.json'):
            raise ValueError('Candidate encoder configuration mismatch')
        if metadata.get('head_sha256') != sha(OUT / 'video_head.joblib'):
            raise ValueError('Candidate classifier checksum mismatch')
        model, processor = load_encoder()
        classifier = joblib.load(OUT / 'video_head.joblib')  # Trusted locally generated artifact only.
        support = float(classifier.predict_proba(feature(args.predict, model, processor)[None])[0, 1])
        print(json.dumps({'status': 'experimental', 'visual_ai_support': support,
                          'decision': 'fake' if support >= .6 else 'real' if support <= .4 else 'inconclusive',
                          'trained_sources': metadata['split_counts']['train'],
                          'warning': 'Uncalibrated visual score. Limited-source prototype; audio sync NOT assessed.'}))
    elif args.prepare_only:
        prepare()
    else:
        train()
