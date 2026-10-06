"""ML inference engine.

Loads model.pth and model_meta.json from RUNS_DIR without downloading weights.
Missing or failed inference is reported explicitly; consumers return an
inconclusive result rather than substituting heuristics for a trained model.
"""
import json
import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import get_settings

settings = get_settings()

_HAS_TORCH = False
try:
    import torch

    _HAS_TORCH = True
except ImportError:
    pass


class MLInference:
    """Wraps a trained Fortexa model for inference on BGR images."""

    def __init__(self, model_path: Path, meta: dict):
        import torch
        self.model_path = Path(model_path)
        self.meta = meta
        self.arch = meta.get("arch", "resnet18")
        self.input_size = meta.get("input_size", 224)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cpu":
            torch.set_num_threads(2)

        # Lazy import to avoid torch dependency at module load
        from .model import build_model
        self.model = build_model(self.arch)
        state = torch.load(self.model_path, map_location=self.device, weights_only=True)
        # Support state dicts saved with or without "module." prefix
        if any(k.startswith("module.") for k in state.keys()):
            state = {k.replace("module.", ""): v for k, v in state.items()}
        self.model.load_state_dict(state)
        self.model.to(self.device)
        self.model.eval()

    def preprocess(self, bgr_image: np.ndarray) -> "torch.Tensor":
        import torch
        from torchvision import transforms
        rgb = bgr_image[:, :, ::-1]
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((self.input_size, self.input_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        tensor = transform(rgb)
        return tensor.unsqueeze(0).to(self.device)

    def predict_prob(self, bgr_image: np.ndarray) -> float:
        """Return fake probability in [0, 1] for a single BGR image."""
        import torch
        if bgr_image is None or bgr_image.size == 0:
            return 0.5
        with torch.no_grad():
            tensor = self.preprocess(bgr_image)
            logit = self.model(tensor)
            prob = torch.sigmoid(logit).item()
        return float(np.clip(prob, 0.0, 1.0))


_engine: Optional[MLInference] = None
_load_lock = threading.RLock()
_load_attempted = False
_load_error = None
logger = logging.getLogger(__name__)


def load_ml_engine(force: bool = False) -> Optional[MLInference]:
    """Load the trained ML engine once. Returns None if not available."""
    global _engine, _load_attempted, _load_error
    with _load_lock:
        return _load_ml_engine_locked(force)


def _load_ml_engine_locked(force: bool = False) -> Optional[MLInference]:
    global _engine, _load_attempted, _load_error
    if _load_attempted and not force:
        return _engine
    _load_attempted = True
    _load_error = None
    if _engine is not None and not force:
        return _engine
    if not _HAS_TORCH:
        _engine = None
        return None

    runs_dir = settings.runs_dir
    model_path = runs_dir / "model.pth"
    meta_path = runs_dir / "model_meta.json"

    if not (model_path.exists() and meta_path.exists()):
        _engine = None
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        _engine = MLInference(model_path, meta)
    except Exception as exc:
        _load_error = str(exc)
        logger.exception("Unable to load detection model")
        _engine = None
    return _engine


def get_ml_status() -> dict:
    """Report detection engine status for health/dashboard endpoints."""
    if settings.DETECTOR_TASK == 'ai-image':
        from .general_image import general_status
        return general_status()
    if not _HAS_TORCH:
        return {
            "status": "unavailable",
            "model": None,
            "torch": False,
            "message": "PyTorch is unavailable; facial classification is inconclusive.",
        }
    eng = load_ml_engine()
    if eng is None:
        return {
            "status": "unavailable",
            "model": None,
            "torch": True,
            "message": "Model failed to load. Check server logs." if _load_error else "No trained model artifact found in runs/.",
        }
    return {
        "status": "ml-face-classifier",
        "model": eng.meta.get("arch", "resnet18"),
        "validation_accuracy": eng.meta.get("val_acc"),
        "test_metrics": eng.meta.get("test_metrics"),
        "manifest_sha256": eng.meta.get("manifest_sha256"),
        "selected_epoch": eng.meta.get("selected_epoch"),
        "evaluation_scope": eng.meta.get("evaluation_scope", "legacy demo data; not independently validated"),
        "dataset": eng.meta.get("dataset_source", "legacy demo dataset"),
        "calibrated": eng.meta.get("calibrated", False),
        "torch": True,
        "trained_at": eng.meta.get("trained_at"),
        "message": f"Face classifier active using {eng.arch} trained model.",
    }


def predict_with_ml(bgr_image: np.ndarray) -> Optional[float]:
    """Predict fake probability using the ML engine, if available."""
    eng = load_ml_engine()
    if eng is None:
        return None
    try:
        return eng.predict_prob(bgr_image)
    except Exception as exc:
        logger.exception("Model prediction failed")
        raise RuntimeError("Model prediction failed; no verdict was generated.") from exc
