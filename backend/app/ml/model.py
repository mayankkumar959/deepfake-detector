"""Neural network model definitions for Fortexa deepfake detection.

Training requires PyTorch + torchvision. Runtime gracefully falls back to
the heuristic engine when no trained artifact / torch is available.
"""
from typing import Optional

try:
    import torch.nn as nn
    import torchvision.models as tv_models

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

    class _DummyModule:
        def __init__(self, *a, **k):
            raise RuntimeError("PyTorch is not installed. Run: pip install -r requirements-ml.txt")


ARCHS = ("tiny", "resnet18", "efficientnet_b0")


def _add_head(model, num_features: int, dropout: float = 0.3):
    import torch.nn as nn
    model.fc = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(num_features, 128),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Linear(128, 1),
    )
    return model


def build_model(arch: str = "resnet18", num_classes: int = 1, dropout: float = 0.3):
    """Build a binary classifier (1 logit for fake probability).

    arch: tiny | resnet18 | efficientnet_b0
    """
    if not _HAS_TORCH:
        raise RuntimeError("PyTorch not installed (pip install -r requirements-ml.txt)")

    arch = arch.lower()
    if arch not in ARCHS:
        raise ValueError(f"Unknown arch '{arch}'. Choose from {ARCHS}")

    if arch == "tiny":
        import torch.nn as nn
        model = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, 1),
        )
        return model

    if arch == "resnet18":
        weights = tv_models.ResNet18_Weights.DEFAULT
        model = tv_models.resnet18(weights=weights)
        return _add_head(model, model.fc.in_features, dropout)

    if arch == "efficientnet_b0":
        weights = tv_models.EfficientNet_B0_Weights.DEFAULT
        model = tv_models.efficientnet_b0(weights=weights)
        model.classifier[1] = __import__("torch.nn").nn.Linear(
            model.classifier[1].in_features, 1
        )
        return model

    raise ValueError(f"Unknown arch '{arch}'")


def get_input_size(arch: str = "resnet18") -> int:
    if arch == "efficientnet_b0":
        return 224
    return 224