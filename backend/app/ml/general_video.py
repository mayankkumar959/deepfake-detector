"""Trained video deepfake detector runtime.

The video head is a small classifier over frozen SigLIP frame statistics plus
source-agnostic texture measurements. It was trained on six frames from the
centred two-second window, so inference reproduces exactly that sampling.

Visual only. Scores are uncalibrated classifier support, not proof of origin.
"""
import hashlib
import json
import threading
from pathlib import Path

import cv2
import joblib
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
from ..config import get_settings
MODEL_ROOT = get_settings().runs_dir.resolve()
VIDEO_HEAD = MODEL_ROOT / 'video_head.joblib'
VIDEO_META = MODEL_ROOT / 'video_meta.json'

FRAMES = 6
WINDOW_SECONDS = 2.0
BORDER_CROP = 0.08
BATCH = 2  # identical features to the six-frame training batch, lower RAM peak

_lock = threading.RLock()
_engine = None
_error = None
_attempted = False


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _aggregate(sequence):
    delta = np.diff(sequence, axis=0)
    return np.concatenate([
        sequence.mean(axis=0),
        sequence.std(axis=0),
        np.abs(delta).mean(axis=0),
    ]).astype(np.float32)


def _texture(images):
    """Same measurements as training; no filename, codec or duration inputs."""
    seq, grays = [], []
    for image in images:
        gray = np.asarray(image.convert('L'), dtype=np.float32) / 255
        grays.append(gray)
        residual = gray - cv2.GaussianBlur(gray, (5, 5), 0)
        gx, gy = np.gradient(gray)
        magnitude = np.sqrt(gx * gx + gy * gy)
        spectrum = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(residual))))
        yy, xx = np.indices(gray.shape)
        radius = np.sqrt((xx - 112) ** 2 + (yy - 112) ** 2) / 159
        rings = [float(spectrum[(radius >= a) & (radius < b)].mean())
                 for a, b in zip(np.linspace(0, 1, 9)[:-1], np.linspace(0, 1, 9)[1:])]
        values = list(np.quantile(np.abs(residual), [.25, .5, .75, .9, .99]))
        values += list(np.quantile(magnitude, [.25, .5, .75, .9, .99])) + rings
        values += [float(gray.std()), float(residual.std()),
                   float(cv2.Laplacian(gray, cv2.CV_32F).var())]
        seq.append(values)
    differences = np.abs(np.diff(np.stack(grays), axis=0))
    return np.concatenate([
        _aggregate(np.array(seq)),
        np.quantile(differences, [.25, .5, .75, .9, .99]),
    ]).astype(np.float32)


def sample_video(path):
    """Six frames from the centred two-second window, as used for training."""
    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('The uploaded video could not be decoded')
    try:
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if count < FRAMES or not np.isfinite(fps) or fps <= 0:
            raise ValueError('Insufficient readable video for temporal screening')
        span = min(count - 1, int(WINDOW_SECONDS * fps))
        start = (count - 1 - span) // 2
        images = []
        for index in np.linspace(start, start + span, FRAMES).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = cap.read()
            if not ok:
                raise ValueError('Could not decode sampled video frame')
            images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    finally:
        cap.release()

    result = []
    for image in images:
        w, h = image.size
        x, y = int(w * BORDER_CROP), int(h * BORDER_CROP)
        result.append(image.crop((x, y, w - x, h - y)).resize((224, 224)))
    if sum(float(np.asarray(image.convert('L')).std()) >= 2 for image in result) < 3:
        raise ValueError('Insufficient visual detail in sampled video frames')
    return result


def _extract(images, vision_model, processor):
    import torch
    with torch.inference_mode():
        chunks = []
        for offset in range(0, len(images), BATCH):
            inputs = processor(images=images[offset:offset + BATCH], return_tensors='pt')
            chunks.append(vision_model(pixel_values=inputs['pixel_values'])
                          .last_hidden_state.mean(dim=1).numpy())
        sequence = np.concatenate(chunks, axis=0)
    return np.concatenate([_aggregate(sequence), _texture(images)])


class VideoDetector:
    def __init__(self):
        self.meta = json.loads(VIDEO_META.read_text(encoding='utf-8'))
        expected = self.meta.get('sha256') or {
            'video_head.joblib': self.meta.get('head_sha256')
        }
        if not expected.get('video_head.joblib'):
            raise ValueError('video_meta.json does not pin the head checksum')
        for name, digest in expected.items():
            if not digest:
                raise ValueError(f'video_meta.json has no checksum for {name}')
            if _sha256(MODEL_ROOT / name) != digest:
                raise ValueError(f'Unverified/incomplete video artifact: {name}')

        # Reuse the image detector's frozen SigLIP tower instead of holding a
        # second 350 MB copy in memory. The image runtime loads first.
        from . import general_image
        image_engine = general_image.load_general_detector()
        if image_engine is None:
            raise RuntimeError('Shared SigLIP encoder is unavailable')
        self._image_lock = general_image._lock
        self.vision_model = image_engine.model.vision_model
        self.processor = image_engine.processor
        self.head = joblib.load(VIDEO_HEAD)
        self.feature_width = int(self.meta['feature_width'])
        self.use_texture = bool(self.meta.get('selected_texture', True))
        expected_width = int(getattr(self.head, 'n_features_in_', self.feature_width))
        if expected_width != self.feature_width:
            raise ValueError('Video head feature width does not match video_meta.json')

        import torch
        torch.set_num_threads(2)
        cv2.setNumThreads(1)

    def predict_prob(self, path):
        images = sample_video(path)
        with self._image_lock:
            values = _extract(images, self.vision_model, self.processor)
        values = values[:self.feature_width]
        probability = float(self.head.predict_proba(values[None])[0, 1])
        if not np.isfinite(probability):
            raise RuntimeError('Video detector returned a non-finite score')
        return probability


def load_video_detector():
    global _engine, _attempted, _error
    with _lock:
        if not _attempted:
            _attempted = True
            if not VIDEO_HEAD.exists() or not VIDEO_META.exists():
                _error = 'video_head.joblib or video_meta.json not packaged'
                import logging
                logging.getLogger(__name__).info(
                    'Trained video detector not configured: %s', _error)
                return None
            try:
                _engine = VideoDetector()
            except Exception as exc:
                _error = str(exc)
                import logging
                logging.getLogger(__name__).exception('Trained video detector unavailable')
        return _engine


def video_status():
    engine = load_video_detector()
    meta = engine.meta if engine else {}
    return {
        'status': 'ml-ai-video-classifier' if engine else 'unavailable',
        'model': meta.get('model') if engine else None,
        'calibrated': False,
        'task': 'AI-generated, face-swap and lip-sync video screening (visual only)',
        'evaluation_scope': meta.get('evaluation_scope') if engine else 'No trained video head loaded',
        'dataset': meta.get('training') if engine else None,
        'test_metrics': meta.get('test_metrics') if engine else None,
        'head_sha256': meta.get('head_sha256') if engine else None,
        'method': meta.get('method') if engine else None,
        'message': ('Trained video head active; score is uncalibrated visual support, '
                    'audio is not assessed.') if engine else
                   f'Video head unavailable: {_error or "artifact missing"}',
    }


def predict_video(path):
    """Return the video-head result, or a non-fatal unavailable fallback."""
    engine = load_video_detector()
    if engine is None:
        return {'used': False, 'reason': _error or 'video artifact missing'}
    try:
        score = engine.predict_prob(path)
    except Exception as exc:
        return {'used': False, 'reason': str(exc)[:300]}
    status = video_status()
    return {
        'used': True,
        'score': round(float(np.clip(score, 0.0, 1.0)), 4),
        'model': status.get('model') or 'SigLIP-Video',
        'head_sha256': status.get('head_sha256'),
        'status': status,
    }
