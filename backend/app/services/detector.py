"""Scan processing orchestrator.

process_scan(scan_id) is the single entry point used by BOTH the Celery worker
and the inline-thread fallback, so behaviour is identical either way.
"""
import json
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from ..config import get_settings
from ..database import SessionLocal
from ..models import ScanRecord
from ..ml.engine import predict_with_ml, get_ml_status
from .image_analysis import analyze_image
from .video_analysis import analyze_video
from .report import build_report
from .face_utils import detect_faces
from . import storage

settings = get_settings()


def _blend_frame_ml(heuristic_prob: float, ml_prob: float | None) -> float:
    if ml_prob is None:
        return heuristic_prob
    return round(0.65 * ml_prob + 0.35 * heuristic_prob, 4)


def _make_heatmap(bgr: np.ndarray, analysis: dict) -> np.ndarray:
    """Annotate the image with face boxes + probability labels."""
    img = bgr.copy()
    faces = detect_faces(bgr)
    fp = analysis["fake_probability"]
    color = (0, 0, 255) if fp >= 0.6 else ((0, 255, 255) if fp >= 0.4 else (0, 255, 0))

    if not faces:
        h, w = img.shape[:2]
        overlay = np.zeros((h, w, 3), dtype=np.uint8)
        intensity = int(180 * fp)
        overlay[:, :] = (intensity, 0, 0)
        img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)
        cv2.putText(img, f"FAKE {fp:.0%}" if fp >= 0.5 else f"REAL {1 - fp:.0%}",
                    (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        return img

    for (x, y, w, h) in faces:
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        label = f"{fp:.0%} fake" if fp >= 0.4 else f"{1 - fp:.0%} real"
        cv2.putText(img, label, (x, max(24, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return img


def process_scan(scan_id: str):
    """Process a scan record (image or video) and persist results."""
    started = time.perf_counter()
    db = SessionLocal()
    try:
        scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
        if scan is None:
            return

        scan.status = "processing"
        db.commit()

        orig_path = scan.original_path
        media_type = scan.media_type
        ml_prob = None

        if media_type == "image":
            bgr = cv2.imread(orig_path)
            if bgr is None:
                raise ValueError("Could not decode image file")
            analysis = analyze_image(bgr, filename=scan.filename)

            # ML blend on the full image + face crop
            ml_prob = predict_with_ml(bgr)
            if ml_prob is not None:
                # Preserve the raw heuristic value for the report
                analysis["_heuristic"] = analysis["fake_probability"]
                faces = detect_faces(bgr)
                if faces:
                    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                    crop = bgr[y:y + h, x:x + w]
                    crop_prob = predict_with_ml(crop)
                    if crop_prob is not None:
                        ml_prob = 0.6 * ml_prob + 0.4 * crop_prob
                analysis["fake_probability"] = _blend_frame_ml(
                    analysis["fake_probability"], ml_prob)

            # Heatmap artifact
            heatmap = _make_heatmap(bgr, analysis)
            ok, buf = cv2.imencode(".jpg", heatmap, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                storage.save_artifact(scan.user_id, scan.id, "heatmap.jpg", buf.tobytes())

        elif media_type == "video":
            analysis = analyze_video(orig_path, filename=scan.filename)

            # ML blend: predict on a small set of sampled frames
            if analysis.get("timeline"):
                analysis["_heuristic"] = analysis["fake_probability"]
                from . import video_analysis as va
                frames, _, _, _ = va._sample_frames(orig_path, max_samples=8)
                ml_probs = []
                for _, frame in frames:
                    mp = predict_with_ml(frame)
                    if mp is not None:
                        ml_probs.append(mp)
                if ml_probs:
                    ml_prob = float(np.mean(ml_probs))
                    analysis["fake_probability"] = _blend_frame_ml(
                        analysis["fake_probability"], ml_prob)

            # Thumbnail artifact
            thumb = analysis.get("thumbnail")
            if thumb is not None:
                ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok:
                    storage.save_artifact(scan.user_id, scan.id, "thumbnail.jpg", buf.tobytes())
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

        ml_status = get_ml_status()
        method = "ml-ensemble" if ml_status["status"] == "ml-ensemble" else "forensic-heuristic"
        model_used = ml_status.get("model", "heuristic-forensic-v1")

        report = build_report(
            media_type=media_type,
            analysis=analysis,
            filename=scan.filename,
            ml_probability=ml_prob,
            method=method,
            model_used=model_used,
        )

        # Persist report.json alongside media artifacts
        scan_dir = storage.scan_dir(scan.user_id, scan.id)
        report_path = scan_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        # Update DB record
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        scan.report = json.dumps(report)
        scan.status = "completed"
        scan.verdict = report["verdict"]
        scan.fake_probability = report["fake_probability"]
        scan.real_probability = report["real_probability"]
        scan.confidence = report["confidence"]
        scan.risk_level = report["risk_level"]
        scan.model_used = report["model_used"]
        scan.method = report["method"]
        scan.error = None
        scan.duration_ms = elapsed_ms
        scan.frame_count = report.get("frame_count")
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        db.rollback()
        scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
        if scan is not None:
            scan.status = "failed"
            scan.error = str(exc)[:2000]
            db.commit()
        import traceback
        traceback.print_exc()
    finally:
        db.close()
