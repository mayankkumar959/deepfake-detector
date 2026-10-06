"""Build the final structured scan report from analysis results."""
from datetime import datetime, timezone
from .image_analysis import SIGNAL_WEIGHTS
from ..ml.engine import get_ml_status

SIGNAL_LABELS = {
    "ela": ("Error Level Analysis", "Detects re-compression / tampering artifacts via JPEG error-level analysis."),
    "frequency": ("Frequency Spectrum", "Analyzes DCT high-frequency energy distribution for GAN smoothing artifacts."),
    "noise": ("Noise Inconsistency", "Compares sensor-noise statistics between face and background regions."),
    "boundary": ("Blending Seams", "Detects edge artifacts / hard splice boundaries around the face region."),
    "color": ("Illumination Mismatch", "Checks color and lighting statistics between face and scene."),
    "metadata": ("Metadata Fingerprint", "Signals editing-software traces in file metadata / naming."),
    "temporal_flicker": ("Temporal Stability", "Measures frame-to-frame luminance flicker for video stability."),
}

RISK_LEVELS = [
    (0.80, "high", "Critical"),
    (0.60, "high", "Elevated"),
    (0.45, "medium", "Moderate"),
    (0.30, "medium", "Caution"),
    (0.00, "low", "Low"),
]


def verdict_for(prob: float) -> str:
    if prob >= 0.6:
        return "fake"
    if prob <= 0.4:
        return "real"
    return "inconclusive"


def risk_for(prob: float) -> tuple[str, str]:
    for threshold, level, label in RISK_LEVELS:
        if prob >= threshold:
            return level, label
    return "low", "Low"


def _summary(prob: float, media_type: str, face_count: int, method: str) -> str:
    verdict = verdict_for(prob)
    level, label = risk_for(prob)
    unit = "image" if media_type == "image" else "video"

    if verdict == "fake":
        return f"The classifier favors the AI-generated class for this {unit} (AI model score {prob:.0%}). This score is not calibrated confidence; review the limitations and original media."
    if verdict == "real":
        return f"The classifier favors the real-photo class for this {unit} (AI model score {prob:.0%}). This does not prove camera origin or exclude other forms of editing."
    return "Classification is inconclusive. The score does not clearly favor either class; review the original media and report limitations."


def build_report(
    media_type: str,
    analysis: dict,
    filename: str,
    ml_probability: float | None,
    method: str,
    model_used: str,
) -> dict:
    """Assemble the complete report JSON persisted with the scan."""
    now = datetime.now(timezone.utc).isoformat()

    # Heuristics are separate diagnostics and never determine the ML verdict.
    heuristic_prob = analysis.get("_heuristic", analysis["fake_probability"])

    # The analysis stores the classifier score, or 0.5 when inconclusive.
    fake_prob = analysis["fake_probability"]

    verdict = verdict_for(fake_prob)
    level, level_label = risk_for(fake_prob)
    real_prob = round(1 - fake_prob, 4)
    confidence = None  # A model score is not calibrated confidence.

    # Build readable signal list
    signals_out = []
    for key, score in analysis["signals"].items():
        label, desc = SIGNAL_LABELS.get(key, (key.replace("_", " ").title(), ""))
        signals_out.append({
            "key": key,
            "label": label,
            "description": desc,
            "score": round(float(score), 4),
            "status": "suspicious" if score >= 0.6 else ("normal" if score <= 0.4 else "neutral"),
            "weight": SIGNAL_WEIGHTS.get(key, 0.0),
        })

    report = {
        "verdict": verdict,
        "risk_level": level,
        "risk_label": level_label,
        "fake_probability": fake_prob,
        "real_probability": real_prob,
        "confidence": confidence,
        "method": method,
        "model_used": model_used,
        "model_evaluation": get_ml_status(),
        "media_type": media_type,
        "filename": filename,
        "signals": signals_out,
        "summary": _summary(fake_prob, media_type, analysis.get("face_count", 0), method),
        "analyzed_at": now,
        "frame_count": analysis.get("frame_count"),
        "duration_seconds": analysis.get("duration_seconds"),
        "analyzed_frames": analysis.get("analyzed_frames"),
        "face_count": analysis.get("face_count", 0),
        "timeline": analysis.get("timeline"),
        "heuristic_probability": heuristic_prob,
        "ml_probability": ml_probability,
        "warnings": analysis.get("warnings", []),
        "score_type": "model_score_not_calibrated_probability",
        "classification_policy": {
            "fake": "AI-generated origin",
            "real": "Real-photo origin",
            "compression_changes_ground_truth": False,
            "diagnostics_determine_verdict": False,
        },
        "classified_frames": analysis.get("classified_frames"),
        "annotation_type": ('ai_score_overlay' if method == 'ml-ai-image-classifier' else 'face_detection_overlay') if media_type == 'image' else 'sampled_frame_thumbnail',
    }
    if analysis.get("warnings") and (ml_probability is None):
        report["summary"] = "Classification is inconclusive. " + " ".join(analysis["warnings"])
        report["risk_label"] = "Undetermined"
    return report
