"""Face detection utilities using OpenCV Haar cascades.

No external model downloads needed; cascade XML ships with opencv-python.
"""
import cv2
import numpy as np

# Cache the cascade classifier
_face_cascade = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade


def detect_faces(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return list of (x, y, w, h) face bounding boxes in the BGR image."""
    if bgr is None or bgr.size == 0:
        return []
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # Equalize histogram for better detection
    gray = cv2.equalizeHist(gray)
    cascade = _get_cascade()
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]


def get_largest_face(bgr: np.ndarray) -> tuple[int, int, int, int]:
    """Return the largest face bounding box, or (0, 0, 0, 0) if none."""
    faces = detect_faces(bgr)
    if not faces:
        return (0, 0, 0, 0)
    # Largest by area
    return max(faces, key=lambda r: r[2] * r[3])


def extract_face_region(bgr: np.ndarray, margin: float = 0.2) -> (np.ndarray, tuple):
    """Crop the largest face region with margin. Returns (crop, [x, y, w, h])."""
    x, y, w, h = get_largest_face(bgr)
    if w == 0:
        return bgr, (0, 0, *bgr.shape[:2][::-1])
    # Expand with margin
    xm = max(0, x - int(w * margin))
    ym = max(0, y - int(h * margin))
    x2 = min(bgr.shape[1], x + w + int(w * margin))
    y2 = min(bgr.shape[0], y + h + int(h * margin))
    return bgr[ym:y2, xm:x2], (xm, ym, x2 - xm, y2 - ym)