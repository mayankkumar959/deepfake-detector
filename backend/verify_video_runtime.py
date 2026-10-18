"""Verify app video inference reproduces training features and predictions.

Run against a packaged RUNS_DIR containing the image model files plus
video_head.joblib/video_meta.json. Reads v2/v3 caches only; never trains.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=Path, default=ROOT / 'runs/active-demo-v2')
parser.add_argument('--manifest', type=Path,
                    default=ROOT / 'data/video-training-v2-20261006/manifest.json')
parser.add_argument('--report', type=Path,
                    default=ROOT / 'runs/candidate-video-v2-20261006/report.json')
parser.add_argument('--full-analysis', action='store_true',
                    help='also run the full analyze_video path (slower)')
args = parser.parse_args()

os.environ['RUNS_DIR'] = str(args.runs.resolve())
os.environ['APP_ENV'] = 'test'
os.environ['DETECTOR_TASK'] = 'ai-image'

from app.ml import general_image, general_video  # noqa: E402
from app.services.video_analysis import analyze_video  # noqa: E402


def pick(rows, label):
    cache = args.report.parent
    for row in rows:
        if row.get('label') != label or row.get('split') != 'test':
            continue
        if not Path(row['path']).is_file():
            continue
        if not (cache / (row['sha256'] + '.npz')).exists():
            continue
        return row
    raise SystemExit(f'No cached test row with label {label}')


def main():
    started = time.time()
    rows = json.loads(args.manifest.read_text())
    report = json.loads(args.report.read_text())
    predictions = {Path(p['path']): p['support'] for p in report['test']['clean']['predictions']}

    image_engine = general_image.load_general_detector()
    if image_engine is None:
        raise SystemExit(f'Image model failed: {general_image._error}')
    video = general_video.load_video_detector()
    if video is None:
        raise SystemExit(f'Video model failed: {general_video._error}')
    print('image + video runtime loaded in', round(time.time() - started, 1), 's')
    print('image:', general_image.general_status()['model'])
    print('video:', general_video.video_status()['model'],
          'width', video.feature_width, 'texture', video.use_texture)

    for label in (0, 1):
        row = pick(rows, label)
        path = Path(row['path'])
        cache = args.report.parent / (row['sha256'] + '.npz')
        with np.load(cache) as data:
            expected = data['clean'][:video.feature_width]
        images = general_video.sample_video(path)
        actual = general_video._extract(images, video.vision_model, video.processor)[:video.feature_width]
        difference = float(np.max(np.abs(actual - expected)))
        relative = difference / max(float(np.max(np.abs(expected))), 1e-6)
        support = float(video.head.predict_proba(actual[None])[0, 1])
        cached_support = predictions.get(path)
        print(f'label={label} source={row["source_model"]} file={path.name}')
        print(f'  max_abs_feature_difference={difference:.6g} relative={relative:.3g}')
        print(f'  runtime_support={support:.6f} report_support={cached_support}')
        if cached_support is not None:
            print(f'  support_difference={abs(support - cached_support):.6g}')
        if difference > 1e-4:
            print('  WARNING: runtime feature vector does not match training cache')
            sys.exit(2)
        if cached_support is not None and abs(support - cached_support) > 1e-5:
            print('  WARNING: runtime head score does not match the report')
            sys.exit(3)
        if args.full_analysis:
            analysis = analyze_video(str(path), filename=path.name)
            print('  analyze_video: fake_probability=', analysis['fake_probability'],
                  'video_used=', analysis['video_model'].get('used'),
                  'frame_ml=', analysis.get('frame_ml_probability'))

    print('OK: runtime matches training features and fresh-test predictions')


if __name__ == '__main__':
    main()
