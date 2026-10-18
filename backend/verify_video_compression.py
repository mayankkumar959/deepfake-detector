"""Actual H.264 transcode stress test; never changes labels or fits the model.

Face-swap records contain selected source frames, not full originals, and are
excluded explicitly. This codec test is NOT an actual WhatsApp transport test.
"""
import argparse
import json
from pathlib import Path
import subprocess

import imageio_ffmpeg
import joblib
import numpy as np

import train_video_candidate as training

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'runs/candidate-video-mixed-20261006'
DATA = ROOT / 'data/video-training-manipulations-20261006/h264-stress'
FILTER = "scale='min(iw,480)':'min(ih,480)':force_original_aspect_ratio=decrease:force_divisible_by=2"


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    rows = json.loads((training.DATA / 'manifest.json').read_text())
    rows += json.loads((DATA.parent / 'lipsync_manifest.json').read_text())
    records = []
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    for row in rows:
        if row['split'] != 'test':
            continue
        source = training.DATA / row['path']
        if training.sha(source) != row['sha256']:
            raise ValueError('Held-out video changed')
        target = DATA / (source.stem + '-crf35.mp4')
        if not target.exists():
            pending = target.with_suffix('.partial.mp4')
            command = [executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-threads', '1',
                       '-i', str(source), '-vf', FILTER, '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
                       '-crf', '35', '-pix_fmt', 'yuv420p', '-threads', '1', '-movflags', '+faststart', str(pending)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeError('Transcode failed: ' + result.stderr[-1000:])
            pending.replace(target)
        training.frames(target)  # Require all six samples to decode.
        records.append({**row, 'original_path': str(source.resolve()), 'compressed_path': str(target.resolve()),
                        'compressed_sha256': training.sha(target)})
        print('H264 transcodes', len(records), '/ 41', flush=True)
    (DATA / 'manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    return records


def verify():
    rows = prepare()
    metadata = json.loads((OUT / 'report.json').read_text())
    if metadata['head_sha256'] != training.sha(OUT / 'video_head.joblib'):
        raise ValueError('Candidate model checksum mismatch')
    if metadata['features']['encoder_sha256'] != training.sha(training.BASE / 'model.safetensors'):
        raise ValueError('Candidate encoder changed')
    if metadata['preprocessor_sha256'] != training.sha(training.BASE / 'preprocessor_config.json'):
        raise ValueError('Candidate processor changed')
    classifier = joblib.load(OUT / 'video_head.joblib')  # Trusted locally trained artifact only.
    model, processor = training.load_encoder()
    probabilities = []
    for i, row in enumerate(rows):
        value = training.feature(Path(row['compressed_path']), model, processor)
        probabilities.append(float(classifier.predict_proba(value[None])[0, 1]))
        print('H264 predictions', i + 1, '/', len(rows), flush=True)
    labels = np.array([r['label'] for r in rows])
    probabilities = np.array(probabilities)
    report = {'status': 'heldout_stress_test_not_used_for_training_or_selection', 'codec': 'libx264',
              'ffmpeg_version': imageio_ffmpeg.get_ffmpeg_version(), 'crf': 35, 'max_edge': 480,
              'preset': 'ultrafast', 'audio': 'removed for BOTH labels; visual-only model',
              'note': 'Not actual WhatsApp compression/transport. Face-swap excluded: only sampled original frames retained.',
              'metrics': training.metrics(labels, probabilities), 'per_source': {},
              'predictions': [{**row, 'visual_ai_support': float(p)} for row, p in zip(rows, probabilities)]}
    for source in sorted({r['source_model'] for r in rows}):
        mask = np.array([r['source_model'] == source for r in rows])
        report['per_source'][source] = training.metrics(labels[mask], probabilities[mask])
    training.save_json(OUT / 'h264_stress_report.json', report)
    print(json.dumps({'metrics': report['metrics'], 'per_source': report['per_source']}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    prepare() if args.prepare_only else verify()
