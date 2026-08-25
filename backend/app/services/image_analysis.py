"""Forensic image analysis (heuristic engine).

Computes several tampering signals on an image:
  1. ELA        — Error Level Analysis (re-compression artifact energy)
  2. FREQ       — DCT high-frequency energy distribution (GAN smoothness)
  3. NOISE      — noise inconsistency between face and background
  4. BOUNDARY   — blending seams / edge artifacts at the face boundary
  5. COLOR      — illumination / color-statistics mismatch
  6. METADATA   — EXIF edit-software fingerprint

Each signal returns score in [0, 1] where HIGHER = MORE LIKELY FAKE.
Signals are combined with a weighted model to produce an overall fake
probability. This engine works with zero ML weights and is used as the
baseline; when a trained model exists, ML output is blended on top.
"""
import io

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageStat

from .face_utils import detect_faces

# Weights for combining signals (sum = 1.0)
SIGNAL_WEIGHTS = {
    "ela": 0.25,
    "frequency": 0.15,
    "noise": 0.20,
    "boundary": 0.20,
    "color": 0.12,
    "metadata": 0.08,
}


# ── Signal: Error Level Analysis ──────────────────────────────────

def _ela_score(bgr: np.ndarray) -> float:
    """Re-save at JPEG q90 and measure mean abs pixel difference."""
    if bgr is None or bgr.size == 0:
        return 0.5
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)

    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")

    diff = ImageChops.difference(pil_img.convert("RGB"), recompressed)
    mean = float(np.mean(np.array(diff.convert("L"))))

    # Normalize: typical real photos ~1-4, tampered regions can exceed 8
    return min(1.0, mean / 12.0)


# ── Signal: Frequency analysis ────────────────────────────────────

def _frequency_score(bgr: np.ndarray) -> float:
    """Analyze DCT high-frequency energy of 8x8 blocks in the face region.

    GAN-generated faces tend to have an unusually smooth / textured mismatch
    in mid-high frequency bands compared to natural camera noise.
    """
    if bgr is None or bgr.size == 0:
        return 0.5
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Prefer the face region when present
    faces = detect_faces(bgr)
    if faces:
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        region = gray[y:y + h, x:x + w]
    else:
        region = gray

    region = cv2.resize(region, (256, 256))

    # Compute DCT energy in 8x8 blocks
    blocks_h = region.shape[0] // 8
    blocks_w = region.shape[1] // 8
    high_freq_energies = []
    for i in range(blocks_h):
        for j in range(blocks_w):
            block = region[i * 8:(i + 1) * 8, j * 8:(j + 1) * 8]
            dct = cv2.dct(block.astype(np.float32))
            abs_dct = np.abs(dct)
            total = abs_dct.sum() + 1e-9
            hi_mask = np.zeros((8, 8), dtype=bool)
            for u in range(8):
                for v in range(8):
                    if (u + v) >= 8:
                        hi_mask[u, v] = True
            high = abs_dct[hi_mask].sum()
            high_freq_energies.append(high / total)

    hf = np.mean(high_freq_energies) if high_freq_energies else 0.5

    # Natural photos sit in a mid band; heavily smoothed GAN faces drop HF
    # while post-processed artifacts raise it. Map deviation from the band.
    deviation = abs(hf - 0.42)
    return min(1.0, deviation / 0.35)


# ── Signal: Noise inconsistency ───────────────────────────────────

def _estimate_noise_std(patch: np.ndarray) -> float:
    """Estimate sensor-noise std via a high-pass detail layer."""
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (128, 128))
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    detail = cv2.absdiff(gray, blurred)
    return float(np.percentile(detail.flatten(), 75))


def _noise_score(bgr: np.ndarray) -> float:
    """Compare noise statistics inside the face vs. the background.

    Spliced / generated faces show different noise profiles than the
    surrounding authentic frame.
    """
    if bgr is None or bgr.size == 0:
        return 0.5
    faces = detect_faces(bgr)
    if not faces:
        return 0.5  # no face → neutral

    h, w = bgr.shape[:2]
    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])

    face_patch = bgr[y:y + fh, x:x + fw]
    if face_patch.size == 0:
        return 0.5

    # Background: region around the face (excluding face box), if available
    bg_patch = None
    m = 20
    bx1, by1 = max(0, x - m), max(0, y - m)
    bx2, by2 = min(w, x + fw + m), min(h, y + fh + m)
    if (bx2 - bx1) > 40 and (by2 - by1) > 40:
        bg_candidates = [
            bgr[by1:by2, bx1:x],
            bgr[by1:by2, x + fw:bx2],
            bgr[by1:y, bx1:bx2],
            bgr[y + fh:by2, bx1:bx2],
        ]
        candidates = [c for c in bg_candidates if c.size > 0]
        if candidates:
            bg_patch = max(candidates, key=lambda c: c.size)

    face_noise = _estimate_noise_std(face_patch)
    if bg_patch is None:
        return 0.5

    bg_noise = _estimate_noise_std(bg_patch)
    ratio = face_noise / (bg_noise + 1e-6)
    deviation = abs(np.log(ratio + 1e-6))
    return min(1.0, deviation / 1.2)


# ── Signal: Boundary / blending artifacts ─────────────────────────

def _boundary_score(bgr: np.ndarray) -> float:
    """Measure edge sharpness discontinuity at the face boundary ring.

    A hard splice produces a crisp edge halo that differs from the interior.
    """
    if bgr is None or bgr.size == 0:
        return 0.5
    faces = detect_faces(bgr)
    if not faces:
        return 0.5

    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Interior patch (central 60% of face box)
    ix1, iy1 = max(0, x + int(fw * 0.2)), max(0, y + int(fh * 0.2))
    ix2, iy2 = min(w, x + int(fw * 0.8)), min(h, y + int(fh * 0.8))

    # Boundary ring (10% expansion around the box)
    bx1, by1 = max(0, x - int(fw * 0.1)), max(0, y - int(fh * 0.1))
    bx2, by2 = min(w, x + fw + int(fw * 0.1)), min(h, y + fh + int(fh * 0.1))

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)

    def edge_strength(r):
        lap = laplacian[r[1]:r[3], r[0]:r[2]]
        return float(np.abs(lap).mean()) if lap.size else 0.0

    interior_edges = edge_strength((ix1, iy1, ix2, iy2))
    ring_edges = edge_strength((bx1, by1, bx2, by2))

    if interior_edges < 1e-6:
        return 0.5

    ratio = ring_edges / interior_edges
    # Natural faces: ring ≈ interior. Spliced: ring >> interior.
    return min(1.0, max(0.0, (ratio - 1.3) / 1.8))


# ── Signal: Color / illumination mismatch ─────────────────────────

def _color_score(bgr: np.ndarray) -> float:
    """Compare HSV statistics of the face vs. non-face background.

    A pasted face often carries lighting from its source scene.
    """
    if bgr is None or bgr.size == 0:
        return 0.5
    faces = detect_faces(bgr)
    if not faces:
        return 0.5

    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    face_patch = hsv[y:y + fh, x:x + fw]

    # Background samples from corners
    corners = [
        hsv[:h // 3, :w // 3],
        hsv[:h // 3, 2 * w // 3:],
        hsv[2 * h // 3:, :w // 3],
        hsv[2 * h // 3:, 2 * w // 3:],
    ]
    corners = [c for c in corners if c.size > 0]
    if not corners or face_patch.size == 0:
        return 0.5

    bg = np.concatenate([c.reshape(-1, 3) for c in corners], axis=0)

    face_mu = face_patch.reshape(-1, 3).astype(np.float32).mean(axis=0)
    bg_mu = bg.astype(np.float32).mean(axis=0)

    # Normalized distance in HSV space
    dist = np.linalg.norm(face_mu - bg_mu) / (255.0 * np.sqrt(3))
    return min(1.0, dist * 2.5)


# ── Signal: Metadata ──────────────────────────────────────────────

EDIT_SOFTWARE_MARKERS = [
    "gimp", "photoshop", "pixlr", "photopea", "adobe", "snapseed", "lightroom",
    "sketch", "canva", "paint.net", "ksnip", "inkscape", "picasa",
]


def _metadata_score(filename: str | None) -> float:
    """Inspect filename for editing-software fingerprints."""
    if not filename:
        return 0.0
    low = filename.lower()
    if any(m in low for m in EDIT_SOFTWARE_MARKERS):
        return 0.7
    if low.startswith(("deepfake", "edit", "screenshot_", "cam_scan")):
        return 0.6
    return 0.0


# ── Public API ────────────────────────────────────────────────────

def analyze_image(bgr: np.ndarray, filename: str | None = None) -> dict:
    """Full heuristic analysis of one image.

    Returns {signals: {...}, fake_probability, face_count}
    """
    ela = _ela_score(bgr)
    freq = _frequency_score(bgr)
    noise = _noise_score(bgr)
    boundary = _boundary_score(bgr)
    color = _color_score(bgr)
    meta = _metadata_score(filename)

    signals = {
        "ela": round(ela, 4),
        "frequency": round(freq, 4),
        "noise": round(noise, 4),
        "boundary": round(boundary, 4),
        "color": round(color, 4),
        "metadata": round(meta, 4),
    }

    weighted = (
        ela * SIGNAL_WEIGHTS["ela"]
        + freq * SIGNAL_WEIGHTS["frequency"]
        + noise * SIGNAL_WEIGHTS["noise"]
        + boundary * SIGNAL_WEIGHTS["boundary"]
        + color * SIGNAL_WEIGHTS["color"]
        + meta * SIGNAL_WEIGHTS["metadata"]
    )

    faces = detect_faces(bgr)
    return {
        "signals": signals,
        "fake_probability": round(float(np.clip(weighted, 0.0, 1.0)), 4),
        "face_count": len(faces),
    }


