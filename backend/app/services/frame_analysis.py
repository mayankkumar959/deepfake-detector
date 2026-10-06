"""Shared image/video decision pipeline. Heuristics are explanatory, not probabilities."""
from ..ml.engine import load_ml_engine, predict_with_ml
from .face_utils import detect_faces, extract_face_region
from .image_analysis import analyze_image


def analyze_frame(bgr):
    from ..config import get_settings
    if get_settings().DETECTOR_TASK == 'ai-image':
        from ..ml.general_image import analyze_general_frame
        return analyze_general_frame(bgr)
    analysis = analyze_image(bgr)
    analysis["_heuristic"] = analysis["fake_probability"]
    analysis["ml_probability"] = None
    analysis["warnings"] = []
    faces = detect_faces(bgr)
    if not faces:
        analysis["fake_probability"] = 0.5
        analysis["warnings"].append("No sufficiently clear face was detected. Facial deepfake classification is inconclusive.")
        return analysis
    if len(faces) > 1:
        analysis["warnings"].append("Only the largest detected face is classified in each image/frame; other faces are not independently assessed.")
    crop, _ = extract_face_region(bgr, margin=0.2)
    probability = predict_with_ml(crop)
    if probability is None:
        analysis["fake_probability"] = 0.5
        analysis["warnings"].append("The trained model is unavailable. Forensic signals alone do not establish authenticity.")
        return analysis
    analysis["ml_probability"] = probability
    analysis["fake_probability"] = round(probability, 4)
    eng = load_ml_engine()
    if not eng.meta.get("independent_evaluation"):
        analysis["warnings"].append("This checkpoint has no independent genuine-deepfake evaluation. Treat this result as experimental.")
    else:
        analysis["warnings"].append("Evaluation scope: " + eng.meta.get("evaluation_scope", "See the model evaluation report."))
    return analysis
