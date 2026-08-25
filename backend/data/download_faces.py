"""Download LFW faces and save as jpg source images for dataset building."""
from pathlib import Path
import cv2
import numpy as np
from sklearn.datasets import fetch_lfw_people

OUT = Path(__file__).parent / "source_faces"
OUT.mkdir(parents=True, exist_ok=True)

print("Downloading LFW (funneled)...")
lfw = fetch_lfw_people(color=True, min_faces_per_person=2, resize=0.5)
images = lfw.images  # (N, H, W, 3) float64 0..1
print(f"Total face images: {len(images)}")

count = 0
for i, img in enumerate(images):
    bgr = (img[:, :, ::-1] * 255).astype(np.uint8)
    # upscale a bit for better downstream resize
    bgr = cv2.resize(bgr, (250, 250))
    cv2.imwrite(str(OUT / f"face_{i:05d}.jpg"), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    count += 1
    if count >= 1200:
        break

print(f"Saved {count} source faces to {OUT}")
