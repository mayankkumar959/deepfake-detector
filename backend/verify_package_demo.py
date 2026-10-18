"""End-to-end demo check for an assembled image+video RUNS_DIR package.

Uploads the local demo samples from data/demo-samples through the real API
(disposable SQLite database and upload storage), waits for each scan and
prints a verdict table. Verifies /api/health reports the packaged image model
and the trained video head. Never deploys, trains or edits the package.

Exit codes: 0 ok (non-fatal mismatches printed), 2 image engine missing,
3 trained video head missing, 4 upload/processing failure, 5 video processed
without the trained head, 6 mismatch under --strict.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=Path, default=ROOT / 'runs/active-image-video-20261018')
parser.add_argument('--samples', type=Path, default=ROOT / 'data/demo-samples')
parser.add_argument('--strict', action='store_true', help='fail on any expected-vs-verdict mismatch')
parser.add_argument('--json', type=Path, default=None, help='optional path to save per-sample results')
parser.add_argument('--timeout', type=float, default=900.0, help='seconds to wait per sample')
args = parser.parse_args()

TEMP = tempfile.TemporaryDirectory(prefix='fortexa-package-e2e-', ignore_cleanup_errors=True)
os.environ.update(
    DETECTOR_TASK='ai-image',
    APP_ENV='test',
    RUNS_DIR=str(args.runs.resolve()),
    DATABASE_URL='sqlite:///' + str(Path(TEMP.name) / 'test.db'),
    UPLOAD_DIR=str(Path(TEMP.name) / 'uploads'),
    SECRET_KEY='isolated-test-secret-' * 4,
    ADMIN_PASSWORD='', CELERY_BROKER_URL='', PYTHONDONTWRITEBYTECODE='1',
)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

HEADERS = {'X-Scan-Session': 'e' * 64}
MEDIA_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
               '.webp': 'image/webp', '.mp4': 'video/mp4', '.mov': 'video/quicktime'}
VIDEO_SUFFIXES = ('.mp4', '.mov')


def expected_for(name):
    if name.startswith('fake_'):
        return 'fake'
    if name.startswith('real_'):
        return 'real'
    return '?'


def wait_for_scan(client, scan_id):
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        response = client.get('/api/scans/' + scan_id, headers=HEADERS)
        response.raise_for_status()
        scan = response.json()
        if scan['status'] in ('completed', 'failed'):
            return scan
        time.sleep(0.5)
    raise TimeoutError(f'scan {scan_id} did not finish within {args.timeout:.0f}s')


def main():
    if not args.samples.is_dir():
        raise SystemExit(f'Missing demo samples folder: {args.samples}')
    if not args.runs.is_dir():
        raise SystemExit(f'Missing runs folder: {args.runs}')
    files = sorted(path for path in args.samples.iterdir()
                   if path.is_file() and path.suffix.lower() in MEDIA_TYPES)
    if not files:
        raise SystemExit(f'No supported media found in {args.samples}')

    results, failures, head_missing, mismatches = [], [], [], []
    images_first = sorted(files, key=lambda p: (p.suffix.lower() in VIDEO_SUFFIXES, p.name))

    with TestClient(app) as client:
        health = client.get('/api/health').json()
        image_engine = health.get('detection_engine') or {}
        video_engine = health.get('video_detection_engine') or {}
        print('health image engine:', image_engine.get('status'), '/', image_engine.get('model'))
        print('health video engine:', video_engine.get('status'), '/', video_engine.get('model'),
              '/ head', str(video_engine.get('head_sha256'))[:12])
        metrics = (video_engine.get('test_metrics') or {}).get('clean') or {}
        if metrics:
            print('  video fresh-test (clean): acc={:.3f} balanced={:.3f} auc={:.3f} examples={}'.format(
                metrics.get('accuracy', float('nan')), metrics.get('balanced_accuracy', float('nan')),
                metrics.get('roc_auc', float('nan')), metrics.get('examples')))
        if image_engine.get('status') != 'ml-ai-image-classifier':
            print('FAIL: packaged image model is not active')
            raise SystemExit(2)
        if video_engine.get('status') != 'ml-ai-video-classifier':
            print('FAIL: trained video head is not active:', video_engine.get('message'))
            raise SystemExit(3)

        for path in images_first:
            expected = expected_for(path.name)
            media = 'video' if path.suffix.lower() in VIDEO_SUFFIXES else 'image'
            upload = client.post('/api/scans', headers=HEADERS,
                                 files={'file': (path.name, path.read_bytes(),
                                                 MEDIA_TYPES[path.suffix.lower()])})
            if upload.status_code != 201:
                failures.append(f'{path.name}: upload {upload.status_code} {upload.text[:200]}')
                print(f'{path.name:<28} FAILED upload ({upload.status_code})')
                continue
            scan = wait_for_scan(client, upload.json()['id'])
            if scan['status'] != 'completed':
                failures.append(f"{path.name}: {scan.get('error', 'processing failed')}")
                print(f"{path.name:<28} FAILED {str(scan.get('error'))[:160]}")
                continue
            report = scan.get('report') or {}
            verdict = scan.get('verdict') or report.get('verdict')
            probability = scan.get('fake_probability', report.get('fake_probability'))
            method = scan.get('method') or report.get('method')
            if verdict == expected:
                match = 'OK'
            elif verdict in ('real', 'fake'):
                match = 'MISMATCH'
                mismatches.append(path.name)
            else:
                match = 'inconclusive'
            head_note = ''
            if media == 'video':
                if method == 'ml-ai-video-classifier':
                    head_note = ' head=YES'
                else:
                    head_note = ' head=NO'
                    head_missing.append(path.name)
            results.append({
                'file': path.name, 'expected': expected, 'media': media,
                'verdict': verdict, 'fake_probability': probability, 'method': method,
                'match': match,
            })
            print(f'{path.name:<28} expected={expected:<5} {media:<5} '
                  f'verdict={str(verdict):<12} fake_probability={probability} '
                  f'method={method}{head_note} [{match}]')

    from app.database import engine as app_engine
    app_engine.dispose()

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print('results saved to', args.json)

    print()
    matched = sum(1 for row in results if row['match'] == 'OK')
    print(f'{matched}/{len(results)} samples match the expected label '
          f'({len(failures)} failures, {len(head_missing)} videos without the head)')
    if failures:
        print('failures:')
        for line in failures:
            print(' -', line)
        raise SystemExit(4)
    if head_missing:
        print('videos processed without the trained head:', ', '.join(head_missing))
        raise SystemExit(5)
    if mismatches and args.strict:
        print('mismatches under --strict:', ', '.join(mismatches))
        raise SystemExit(6)
    if mismatches:
        print('note: uncalibrated demo mismatches (not fatal):', ', '.join(mismatches))
    print('OK: packaged image model + trained video head processed all demo samples')


if __name__ == '__main__':
    main()
