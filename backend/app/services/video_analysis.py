"""Video deepfake analysis.

Strategy:
  1. Sample up to N frames evenly across the video.
  2. Run per-frame forensic analysis (face-aware) → per-frame fake probability.
  3. Compute temporal stability signals (flicker across frames).
  4. Aggregate into a final probability + timeline for the UI.
"""
import cv2
import numpy as np

from .face_utils import detect_faces
from .frame_analysis import analyze_frame
from ..config import get_settings

MAX_SAMPLES = 16


def _sample_frames(video_path: str, max_samples: int = MAX_SAMPLES) -> tuple[list[tuple[float, np.ndarray]], float, float, int]:
    """Return [(timestamp_sec, frame_bgr), ...] sampled evenly."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("The uploaded video could not be decoded")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration = total_frames / fps if fps else 0.0
    if duration > get_settings().MAX_VIDEO_SECONDS:
        cap.release()
        raise ValueError(f"Video exceeds the {get_settings().MAX_VIDEO_SECONDS}-second processing limit")

    if total_frames <= 0:
        cap.release()
        return [], duration, fps, 0

    indices = np.linspace(0, total_frames - 1, min(max_samples, total_frames), dtype=int).tolist()

    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append((idx / fps, frame))
    cap.release()
    return frames, duration, fps, total_frames


def _temporal_flicker_score(frames: list[np.ndarray]) -> float:
    """Estimate flicker = variance of inter-frame luminance change.

    Deepfake generators often produce temporal instability in the face area.
    """
    if len(frames) < 2:
        return 0.5
    diffs = []
    for a, b in zip(frames[:-1], frames[1:]):
        try:
            ga = cv2.cvtColor(cv2.resize(a, (256, 256)), cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(cv2.resize(b, (256, 256)), cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(ga, gb).mean()
            diffs.append(float(diff))
        except Exception:
            continue
    if not diffs:
        return 0.5
    mean_diff = float(np.mean(diffs))
    # Stability: frame-to-frame change should be low & smooth for authentic video
    if mean_diff > 14.0:
        return 0.8
    if mean_diff > 8.0:
        return 0.6
    if mean_diff < 2.0:
        return 0.65  # suspiciously static (frozen face)
    return 0.25  # natural motion


def analyze_video(video_path: str, filename: str | None = None) -> dict:
    """Full video analysis. Returns a rich dict for the report builder."""
    frames, duration, fps, total_frames = _sample_frames(video_path)

    if not frames:
        raise ValueError("No readable frames found in video")

    timeline = []
    aggregate_signals = {}
    ml_probs = []
    warnings = set()
    max_faces = 0
    heuristic_probs = []

    for ts, frame in frames:
        result = analyze_frame(frame)
        heuristic_probs.append(result["_heuristic"])
        max_faces = max(max_faces, result["face_count"])
        warnings.update(result.get("warnings", []))
        if result.get("ml_probability") is not None:
            ml_probs.append(result["ml_probability"])

        # Each timeline entry uses the same classifier as the final aggregate.
        fp = result["fake_probability"]
        timeline.append({
            "index": len(timeline),
            "time": round(ts, 2),
            "fake_probability": fp,
            "classified": result.get("ml_probability") is not None,
            "face_count": result["face_count"],
            "verdict": "fake" if fp >= 0.6 else ("real" if fp <= 0.4 else "inconclusive"),
        })

        # Merge signals (average)
        for key, val in result["signals"].items():
            if key not in aggregate_signals:
                aggregate_signals[key] = []
            aggregate_signals[key].append(val)

    signals = {k: round(float(np.mean(v)), 4) for k, v in aggregate_signals.items()}

    # Temporal flicker signal
    flicker = _temporal_flicker_score([f for _, f in frames])
    signals["temporal_flicker"] = round(flicker, 4)

    # Motion, lighting and scene cuts are not calibrated deepfake evidence.
    combined = float(np.mean(ml_probs)) if ml_probs else 0.5
    if ml_probs:
        warnings.add(f"Only {len(ml_probs)} of {len(frames)} sampled frames were classified. Unseen frames and audio were not assessed.")

    # Thumbnail: frame with a detected face (or middle frame)
    thumbnail = None
    for _, frame in frames:
        if detect_faces(frame):
            thumbnail = frame
            break
    if thumbnail is None:
        thumbnail = frames[len(frames) // 2][1]

    return {
        "fake_probability": round(float(np.clip(combined, 0.0, 1.0)), 4),
        "signals": signals,
        "timeline": timeline,
        "frame_count": total_frames,
        "duration_seconds": round(duration, 2),
        "fps": round(fps, 2),
        "thumbnail": thumbnail,
        "analyzed_frames": len(frames),
        "classified_frames": len(ml_probs),
        "face_count": max_faces,
        "ml_probability": float(np.mean(ml_probs)) if ml_probs else None,
        "_heuristic": float(np.mean(heuristic_probs)),
        "warnings": sorted(warnings),
    }
