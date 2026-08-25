"""Demo dataset generator.

Creates a small real/fake training set from any folder of face images:
- real/  → untouched copies
- fake/  → GAN-style artifact injections (local blur, JPEG re-compression,
           noise, color shifts, blending seams) applied to copies
"""
import argparse
import random
from pathlib import Path

import cv2
import numpy as np

from tqdm import tqdm


def inject_fake_artifacts(img: np.ndarray, seed: int) -> np.ndarray:
    """Apply a random combination of deepfake-like artifacts."""
    rng = random.Random(seed)
    out = img.copy()
    h, w = out.shape[:2]

    # 1. Slight global softening (GAN smoothness)
    if rng.random() < 0.7:
        k = rng.choice([5, 7])
        out = cv2.GaussianBlur(out, (k, k), 0)

    # 2. Re-compression
    for _ in range(rng.randint(1, 3)):
        enc = rng.choice([".jpg", ".jpg", ".webp"])
        out = recompress(out, enc, rng.randint(60, 90))

    # 3. Local blur patch (face area)
    if rng.random() < 0.8:
        x = rng.randint(0, max(1, w // 3))
        y = rng.randint(0, max(1, h // 3))
        pw, ph = w // 3, h // 3
        roi = out[y:y + ph, x:x + pw]
        out[y:y + ph, x:x + pw] = cv2.GaussianBlur(roi, (11, 11), 0)

    # 4. Color shift (hue/sat)
    if rng.random() < 0.6:
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[:, :, 0] = np.clip(hsv[:, :, 0].astype(int) + rng.randint(-15, 15), 0, 179).astype(np.uint8)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(int) * rng.uniform(0.85, 1.15), 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    # 5. Random noise / artifacts
    if rng.random() < 0.5:
        noise = np.random.normal(0, rng.uniform(3, 12), out.shape).astype(np.int16)
        out = np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # 6. Splicing seam: high-contrast edge box
    if rng.random() < 0.5:
        x, y = rng.randint(5, max(6, w // 2)), rng.randint(5, max(6, h // 2))
        cv2.rectangle(out, (x, y), (x + w // 4, y + h // 4), (0, 0, 0), 2)

    return out


def recompress(img: np.ndarray, ext: str, quality: int) -> np.ndarray:
    """Encode/decode an image to simulate compression."""
    if ext == ".jpg":
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR) if ok else img
    if ext == ".webp":
        ok, buf = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, quality])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR) if ok else img
    return img


def build_dataset(source_dir: Path, out_dir: Path, per_class: int = 100):
    """Build real/fake dataset from source images."""
    source_dir = Path(source_dir)
    out_dir = Path(out_dir)
    real_dir = out_dir / "real"
    fake_dir = out_dir / "fake"
    real_dir.mkdir(parents=True, exist_ok=True)
    fake_dir.mkdir(parents=True, exist_ok=True)

    sources = [p for p in source_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not sources:
        raise SystemExit(f"No images found in {source_dir}")

    rng = random.Random(42)
    print(f"Source images: {len(sources)} → creating {per_class} real + {per_class} fake")

    used = 0
    for i in tqdm(range(per_class), desc="real"):
        src = rng.choice(sources)
        img = cv2.imread(str(src))
        if img is None:
            continue
        out = cv2.resize(img, (224, 224))
        cv2.imwrite(str(real_dir / f"real_{i:05d}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        used += 1

    for i in tqdm(range(per_class), desc="fake"):
        src = rng.choice(sources)
        img = cv2.imread(str(src))
        if img is None:
            continue
        img = cv2.resize(img, (224, 224))
        fake = inject_fake_artifacts(img, seed=i)
        cv2.imwrite(str(fake_dir / f"fake_{i:05d}.jpg"), fake, [cv2.IMWRITE_JPEG_QUALITY, 92])
        used += 1

    print(f"Dataset written to {out_dir} ({used} samples)")
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Generate demo real/fake dataset")
    parser.add_argument("--source", type=str, required=True, help="Folder with any face/photo images")
    parser.add_argument("--out", type=str, default="./data/demo_dataset")
    parser.add_argument("--per-class", type=int, default=100)
    args = parser.parse_args()
    build_dataset(Path(args.source), Path(args.out), args.per_class)


if __name__ == "__main__":
    main()