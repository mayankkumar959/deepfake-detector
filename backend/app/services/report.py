"""Build the final structured scan report from analysis results."""
from datetime import datetime, timezone

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
        if prob >= 0.8:
            return (f"High-confidence indication of manipulated media. Multiple forensic signals "
                    f"point to synthetic generation or tampering ({int(prob * 100)}% fake probability).")
        return (f"Forensic signals suggest this {unit} may have been manipulated "
                f"({int(prob * 100)}% fake probability). Manual review recommended.")
    if verdict == "real":
        return (f"No significant tampering artifacts detected. This {unit} appears consistent with "
                f"authentic capture ({int((1 - prob) * 100)}% real probability).")
    return (f"Results are inconclusive. Signals do not strongly favor either class "
            f"({int(prob * 100)}% fake). Review the signal breakdown for details.")


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

    # Heuristic probability (pre-blend value recorded by the detector)
    heuristic_prob = analysis.get("_heuristic", analysis["fake_probability"])

    # analysis["fake_probability"] is ALREADY the final blended probability —
    # the detector blends ML into it before calling build_report.
    fake_prob = analysis["fake_probability"]

    verdict = verdict_for(fake_prob)
    level, level_label = risk_for(fake_prob)
    real_prob = round(1 - fake_prob, 4)
    confidence = round(max(fake_prob, real_prob), 4)

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
            "weight": round(
                (0.25 if key == "ela" else 0.15 if key == "frequency"
                 else 0.20 if key in ("noise", "boundary")
                 else 0.12 if key == "color"
                 else 0.10), 2),
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
    }
    return report