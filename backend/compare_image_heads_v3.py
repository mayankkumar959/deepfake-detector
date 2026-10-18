"""Apples-to-apples image head comparison on the v3 fresh test.

Recomputes the v3 candidate head and the v2 candidate head on the identical
cached v3 test features (same frozen encoder, same four views). The v3 head
must reproduce report.json exactly first; then the v2 head gets the same test.
Read-only: never trains, edits or deploys anything.

Usage:
  python compare_image_heads_v3.py
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--v3', type=Path, default=ROOT / 'runs/candidate-image-v3-20261018')
parser.add_argument('--v2', type=Path, default=ROOT / 'runs/candidate-image-v2-20261006')
parser.add_argument('--manifest', type=Path,
                    default=ROOT / 'data/general-ai-training-v3-20261018/manifest.json')
args = parser.parse_args()

VIEWS = ('clean', 'jpeg90', 'resize768_jpeg55', 'resize512_jpeg40')


def main():
    import train_video_candidate as shared

    rows = json.loads(args.manifest.read_text(encoding='utf-8'))
    rows = [row for row in rows if row['split'] == 'test']
    labels = np.array([row['label'] for row in rows])
    features = np.stack([np.load(args.v3 / (row['sha256'] + '.npz'))['features']
                         for row in rows])
    print(f'test rows: {len(rows)}  features: {features.shape}  '
          f'classes: {int((labels == 0).sum())} real / {int((labels == 1).sum())} fake')

    report = json.loads((args.v3 / 'report.json').read_text(encoding='utf-8'))
    heads = [('v3 candidate', args.v3 / 'image_head.joblib'),
             ('v2 candidate', args.v2 / 'image_head.joblib')]
    failures = []
    for name, path in heads:
        head = joblib.load(path)
        print(f'\n== {name} ({path.name}) ==')
        for index, view_name in enumerate(VIEWS):
            scores = head.predict_proba(features[:, index])[:, 1]
            metric = shared.metrics(labels, scores)
            metric.pop('videos')
            line = (f"{view_name:<18} acc={metric['accuracy']:.4f} "
                    f"bal={metric['balanced_accuracy']:.4f} auc={metric['roc_auc']:.4f} "
                    f"ff={metric['false_fake_decisions']} fr={metric['false_real_decisions']}")
            if name.startswith('v3'):
                reference = report['test'][view_name]['candidate']
                ok = (abs(metric['accuracy'] - reference['accuracy']) < 1e-9
                      and abs(metric['roc_auc'] - reference['roc_auc']) < 1e-9)
                line += '  [reproduces report]' if ok else '  [REPORT MISMATCH]'
                if not ok:
                    failures.append(view_name)
            print(' ', line)
    if failures:
        raise SystemExit('v3 head did not reproduce the report for: ' + ', '.join(failures))
    print('\nOK: v3 head reproduces report.json; v2 head scored on the same v3 test.')


if __name__ == '__main__':
    main()
