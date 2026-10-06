"""General AI versus real image detector, verified offline pretrained runtime.

Uses the publisher's image processor and classifier without face cropping.
Scores are not calibrated probabilities. Compression does not change ground truth.
"""
import hashlib
import json
from pathlib import Path
import threading

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
from ..config import get_settings
MODEL_ROOT = get_settings().runs_dir.resolve()
_lock = threading.RLock()
_engine = None
_error = None
_attempted = False


class GeneralImageDetector:
    def __init__(self):
        self.meta = json.loads((MODEL_ROOT / 'model_meta.json').read_text())
        for name, expected in self.meta['sha256'].items():
            digest = hashlib.sha256()
            with (MODEL_ROOT / name).open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f'Unverified/incomplete model artifact: {name}')
        torch.set_num_threads(2)
        from transformers import AutoImageProcessor, SiglipForImageClassification
        self.processor = AutoImageProcessor.from_pretrained(str(MODEL_ROOT), local_files_only=True, trust_remote_code=False, use_fast=False)
        self.model = SiglipForImageClassification.from_pretrained(str(MODEL_ROOT), local_files_only=True, use_safetensors=True)
        self.model.eval()
        labels = self.model.config.id2label
        ai_indices = [int(index) for index, label in labels.items() if label.lower() == 'ai']
        if len(ai_indices) != 1 or len(labels) != 2 or 'hum' not in [label.lower() for label in labels.values()]:
            raise ValueError('Unexpected model label mapping; refusing to reverse real/AI labels')
        self.ai_index = ai_indices[0]

    def predict_prob(self, bgr):
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        inputs = self.processor(images=Image.fromarray(rgb), return_tensors='pt')
        with torch.inference_mode(), _lock:
            if torch.get_num_threads() != 2:
                torch.set_num_threads(2)
            score = self.model(**inputs).logits.softmax(dim=-1)[0, self.ai_index].item()
        if not np.isfinite(score):
            raise RuntimeError('AI-image detector returned a non-finite score')
        return float(score)


def load_general_detector():
    global _engine, _attempted, _error
    with _lock:
        if not _attempted:
            _attempted = True
            try:
                _engine = GeneralImageDetector()
            except Exception as exc:
                _error = str(exc)
                import logging
                logging.getLogger(__name__).exception('General AI-image detector unavailable')
        return _engine


def general_status():
    engine = load_general_detector()
    return {
        'status': 'ml-ai-image-classifier' if engine else 'unavailable',
        'model': 'SigLIP-AI-vs-human' if engine else None,
        'calibrated': False, 'task': 'AI-generated versus real image; not generic edit detection',
        'evaluation_scope': engine.meta.get('evaluation_scope', 'Published pretrained model; local representative cross-generator/compression benchmark pending.') if engine else 'No general model loaded',
        'dataset': engine.meta.get('training', 'See model metadata') if engine else None,
        'test_metrics': engine.meta.get('test_metrics') if engine else None, 'validation_accuracy': None,
        'manifest_sha256': engine.meta.get('manifest_sha256') if engine else None,
        'message': 'AI-image detector active; model score is not proof of origin.' if engine else 'General AI-image weights/code missing or incompatible; see server logs.',
    }


def analyze_general_frame(bgr):
    from ..services.image_analysis import analyze_image
    analysis = analyze_image(bgr)
    analysis['_heuristic'] = analysis['fake_probability']
    analysis['fake_probability'] = .5
    analysis['ml_probability'] = None
    analysis['warnings'] = [
        'Scores indicate AI-generation evidence, not calibrated confidence or proof of authenticity.',
        'Real-image compression does not make an image AI-generated. AI images remain AI-generated after compression.',
        'Generic Photoshop/content-edit detection is outside this model\'s scope.',
        'Evaluation scope: small full-image training study; representative cross-generator/compression validation is still pending.',
    ]
    if min(bgr.shape[:2]) < 224 or float(bgr.std()) < 2:
        analysis['warnings'].append('Image is too small or has insufficient visual detail for reliable classification. Result is inconclusive.')
        return analysis
    engine = load_general_detector()
    if engine is None:
        analysis['warnings'].append('General AI-image model is unavailable. No trained fallback verdict is substituted.')
        return analysis
    score = engine.predict_prob(bgr)
    analysis['ml_probability'] = score
    analysis['fake_probability'] = round(score, 4)
    return analysis
