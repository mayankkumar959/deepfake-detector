"""Assemble a deployable image+video run directory (local-only, no activation).

Copies only the four image model files and the two video head artifacts, never
feature caches. The resulting directory can be used directly as RUNS_DIR or as
the Docker MODEL_DIR. This script never edits .env or deploys anything.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parent
IMAGE_FILES = ('model.safetensors', 'config.json', 'preprocessor_config.json', 'model_meta.json')
VIDEO_FILES = ('video_head.joblib', 'video_meta.json')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path,
                        default=ROOT / 'runs/candidate-image-v3-20261018/compatible_model')
    parser.add_argument('--video', type=Path,
                        default=ROOT / 'runs/candidate-video-v3-20261018')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'runs/active-image-video-20261018')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    missing = [name for name in IMAGE_FILES if not (args.image / name).is_file()]
    missing += [name for name in VIDEO_FILES if not (args.video / name).is_file()]
    if missing:
        raise SystemExit(f'Missing artifacts: {missing}')

    image_meta = json.loads((args.image / 'model_meta.json').read_text(encoding='utf-8'))
    for name, expected in image_meta.get('sha256', {}).items():
        if sha256(args.image / name) != expected:
            raise SystemExit(f'Image artifact checksum mismatch: {name}')

    video_meta = json.loads((args.video / 'video_meta.json').read_text(encoding='utf-8'))
    for name, expected in video_meta.get('sha256', {}).items():
        if sha256(args.video / name) != expected:
            raise SystemExit(f'Video artifact checksum mismatch: {name}')
    if int(video_meta.get('feature_width', 0)) <= 0:
        raise SystemExit('video_meta.json has no valid feature_width')

    if args.out.exists():
        if not args.force:
            raise SystemExit(f'Output exists: {args.out} (use --force to replace)')
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    for source in (args.image, args.video):
        for name in IMAGE_FILES + VIDEO_FILES:
            path = source / name
            if path.is_file():
                shutil.copy2(path, args.out / name)

    packaged_meta = dict(image_meta)
    packaged_meta['active'] = True
    packaged_meta['activation'] = {
        'activated': True,
        'packaged_at_unix': time.time(),
        'image_source': str(args.image),
        'video_source': str(args.video),
        'video_model': video_meta.get('model'),
        'video_head_sha256': video_meta.get('head_sha256'),
        'video_test_metrics_clean': video_meta.get('test_metrics', {}).get('clean'),
    }
    (args.out / 'model_meta.json').write_text(json.dumps(packaged_meta, indent=2), encoding='utf-8')

    files = {}
    for name in IMAGE_FILES + VIDEO_FILES:
        path = args.out / name
        if path.is_file():
            files[name] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    package = {
        'created_at_unix': time.time(),
        'purpose': 'Local image+video deployment package; no cloud upload performed',
        'model.safetensors_sha256': files['model.safetensors']['sha256'],
        'video_head.joblib_sha256': files['video_head.joblib']['sha256'],
        'image_test_metrics': image_meta.get('test_metrics'),
        'video_test_metrics': video_meta.get('test_metrics'),
        'files': files,
    }
    (args.out / 'PACKAGE.json').write_text(json.dumps(package, indent=2), encoding='utf-8')

    print('packaged:', args.out)
    print('model_meta active:', packaged_meta['active'])
    print('video head sha256:', files['video_head.joblib']['sha256'])
    print('Docker ARG MODEL_WEIGHTS_SHA256=' + files['model.safetensors']['sha256'])


if __name__ == '__main__':
    main()
