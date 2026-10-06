"""Regression checks using disposable storage, plus a synthetic training smoke test."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
TEMP = tempfile.TemporaryDirectory(prefix="fortexa-product-test-")
TEMP_ROOT = Path(TEMP.name)
os.environ.update(DATABASE_URL="sqlite:///" + str(TEMP_ROOT / "test.db"),
                  UPLOAD_DIR=str(TEMP_ROOT / "uploads"), RUNS_DIR=os.environ.get("FORTEXA_TEST_RUNS_DIR", str(ROOT / "runs/candidate-dff-finetuned-20261005")),
                  APP_ENV="test", SECRET_KEY="test-only-" * 8, ADMIN_PASSWORD="",
                  CELERY_BROKER_URL="", PYTHONDONTWRITEBYTECODE="1")
os.environ['DETECTOR_TASK'] = 'legacy-face'  # Historical face pipeline regression only; not general-AI validation.

import cv2
import numpy as np
import torch
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine
from app.models import ScanRecord
from app.services.celery_app import _pool
from app.services.retention import purge_expired_scans
from app.services.image_analysis import analyze_image
from app.ml.train_manifest import load_manifest, train

torch.set_num_threads(2)
SESSION_A = {"X-Scan-Session": "a" * 64}
SESSION_B = {"X-Scan-Session": "b" * 64}


class ProductTests(unittest.TestCase):
    def test_health_distinguishes_missing_model(self):
        with patch("app.routers.health.get_ml_status", return_value={"status": "unavailable"}):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "connected")
        self.assertEqual(response.json()["status"], "degraded")

    def test_active_checkpoint_loads(self):
        from app.ml.engine import load_ml_engine, get_ml_status
        model = load_ml_engine()
        self.assertIsNotNone(model, "Configured checkpoint failed to load")
        self.assertEqual(get_ml_status()["status"], "ml-face-classifier")
        score = model.predict_prob(np.zeros((224, 224, 3), dtype=np.uint8))
        self.assertTrue(np.isfinite(score) and 0 <= score <= 1)

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def upload(self, filename, data, content_type, expected=201):
        response = self.client.post("/api/scans", headers=SESSION_A, files={"file": (filename, data, content_type)})
        self.assertEqual(response.status_code, expected, response.text)
        if expected != 201:
            return response
        scan_id = response.json()["id"]
        for _ in range(200):
            response = self.client.get(f"/api/scans/{scan_id}", headers=SESSION_A)
            self.assertEqual(response.status_code, 200, response.text)
            if response.json()["status"] in ("completed", "failed"):
                return response.json()
            time.sleep(.05)
        self.fail("Scan processing did not finish")

    def test_blank_image_is_inconclusive_and_private(self):
        _, data = cv2.imencode(".jpg", np.zeros((224, 224, 3), dtype=np.uint8))
        scan = self.upload("blank.jpg", data.tobytes(), "image/jpeg")
        self.assertEqual(scan["status"], "completed")
        self.assertEqual(scan["verdict"], "inconclusive")
        self.assertEqual(scan["fake_probability"], .5)
        self.assertIsNone(scan["confidence"])
        self.assertTrue(scan["report"]["warnings"])
        path = f"/api/scans/{scan['id']}"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers=SESSION_B).status_code, 404)
        self.assertEqual(self.client.delete(path, headers=SESSION_B).status_code, 404)
        self.assertEqual(self.client.get("/api/scans", headers=SESSION_B).json()["total"], 0)
        self.assertEqual(self.client.get(path + "/media/original").status_code, 404)
        self.assertEqual(self.client.get(path + "/media/original?token=invalid").status_code, 404)
        token = scan["media_token"]
        original = self.client.get(path + f"/media/original?token={token}")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.headers["cache-control"], "private, no-store")
        self.assertEqual(self.client.get(path + f"/media/heatmap.jpg?token={token}").status_code, 200)
        self.assertEqual(self.client.get(path + f"/media/report.json?token={token}").status_code, 200)
        self.assertEqual(self.client.delete(path, headers=SESSION_A).status_code, 204)
        self.assertEqual(self.client.get(path, headers=SESSION_A).status_code, 404)

    def test_upload_validation(self):
        self.upload("corrupt.jpg", b"not an image", "image/jpeg", expected=400)
        self.upload("empty.jpg", b"", "image/jpeg", expected=400)
        self.upload("bad.txt", b"text", "text/plain", expected=400)
        response = self.client.post("/api/scans", files={"file": ("photo.jpg", b"bad", "image/jpeg")})
        self.assertEqual(response.status_code, 401)

    def test_clear_face_uses_model_with_evaluation_warning(self):
        manifest_path = Path(os.environ.get("FORTEXA_TEST_GENUINE_MANIFEST", str(ROOT / "data/genuine_dff/manifest.json")))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        from app.services.face_utils import detect_faces
        rows = [r for r in manifest["records"] if r["split"] == "test" and r["label"] == 0]
        path = next((manifest_path.parent / r["path"] for r in rows[:30]
                     if (img := cv2.imread(str(manifest_path.parent / r["path"]))) is not None and detect_faces(img)), None)
        self.assertIsNotNone(path, "Genuine held-out clear-face fixture is required")
        scan = self.upload("face.png", path.read_bytes(), "image/png")
        self.assertEqual(scan["status"], "completed", scan.get("error"))
        self.assertGreater(scan["report"]["face_count"], 0)
        self.assertIsNotNone(scan["report"]["ml_probability"])
        self.assertEqual(scan["method"], "ml-face-classifier")
        self.assertTrue(any("experimental" in warning or "Evaluation scope:" in warning for warning in scan["report"]["warnings"]))

    def test_registration_does_not_grant_admin(self):
        response = self.client.post("/api/auth/register", json={"email": "auditor@example.com", "username": "auditor", "password": "test-password-123"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["role"], "user")
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/users", headers=headers).status_code, 403)

    @unittest.skipUnless(os.environ.get("FORTEXA_TEST_GENUINE_MANIFEST"), "Optional genuine holdout integration check")
    def test_genuine_holdout_originals_through_api(self):
        manifest = json.loads(Path(os.environ["FORTEXA_TEST_GENUINE_MANIFEST"]).read_text(encoding="utf-8"))
        rows = [r for r in manifest["records"] if r["split"] == "test"][:6]
        self.assertEqual({r["label"] for r in rows}, {0, 1})
        from app.ml.engine import load_ml_engine
        from app.services.face_utils import extract_face_region
        model = load_ml_engine()
        self.assertTrue(model.meta.get("independent_evaluation"))
        for row in rows:
            archive_path = ROOT / "data/archives" / ("wiki.zip" if row["label"] == 0 else "inpainting.zip")
            with zipfile.ZipFile(archive_path) as archive:
                data = archive.read(row["original_file"])
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            crop, _ = extract_face_region(image, margin=.2)
            expected_score = model.predict_prob(crop)
            scan = self.upload(Path(row["original_file"]).name, data, "image/jpeg")
            self.assertEqual(scan["status"], "completed", scan.get("error"))
            self.assertEqual(scan["method"], "ml-face-classifier")
            self.assertAlmostEqual(scan["fake_probability"], expected_score, places=3)
            self.assertTrue(any("Evaluation scope:" in w for w in scan["report"]["warnings"]))
            self.assertEqual(self.client.get(f"/api/scans/{scan['id']}", headers=SESSION_B).status_code, 404)
            print(json.dumps({"integration_holdout_label": row["label"], "fake_model_score": scan["fake_probability"]}), flush=True)

    @unittest.skipUnless(os.environ.get("FORTEXA_TEST_GENUINE_MANIFEST"), "Optional genuine face-video integration check")
    def test_genuine_face_video_uses_candidate(self):
        manifest = json.loads(Path(os.environ["FORTEXA_TEST_GENUINE_MANIFEST"]).read_text(encoding="utf-8"))
        from app.services.face_utils import detect_faces
        for label in (0, 1):
            rows = [r for r in manifest["records"] if r["split"] == "test" and r["label"] == label]
            image = next((img for r in rows[:30] if (img := cv2.imread(str(Path(os.environ["FORTEXA_TEST_GENUINE_MANIFEST"]).parent / r["path"]))) is not None and detect_faces(img)), None)
            self.assertIsNotNone(image, "No suitable face fixture")
            path = TEMP_ROOT / f"face-{label}.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 6, (224, 224))
            self.assertTrue(writer.isOpened())
            for _ in range(6):
                writer.write(image)
            writer.release()
            scan = self.upload(path.name, path.read_bytes(), "video/x-msvideo")
            self.assertEqual(scan["status"], "completed", scan.get("error"))
            self.assertEqual(scan["method"], "ml-face-classifier")
            self.assertGreater(scan["report"]["classified_frames"], 0)
            self.assertTrue(all("classified" in entry for entry in scan["report"]["timeline"]))

    def test_filename_does_not_change_score(self):
        image = np.random.default_rng(42).integers(0, 255, (128, 128, 3), dtype=np.uint8)
        self.assertEqual(analyze_image(image, "photo.jpg"), analyze_image(image, "photoshop.jpg"))

    def test_missing_model_is_inconclusive(self):
        from app.services.frame_analysis import analyze_frame
        from app.ml.engine import get_ml_status
        image = np.zeros((128, 128, 3), dtype=np.uint8)
        with patch("app.services.frame_analysis.detect_faces", return_value=[(10, 10, 80, 80)]), patch("app.services.frame_analysis.extract_face_region", return_value=(image, (0, 0, 128, 128))), patch("app.services.frame_analysis.predict_with_ml", return_value=None):
            analysis = analyze_frame(image)
        self.assertEqual(analysis["fake_probability"], .5)
        self.assertIsNone(analysis["ml_probability"])
        self.assertTrue(any("unavailable" in w for w in analysis["warnings"]))
        with patch("app.ml.engine._HAS_TORCH", False):
            self.assertEqual(get_ml_status()["status"], "unavailable")

    def test_video_contract_and_thumbnail(self):
        path = TEMP_ROOT / "blank.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 6, (224, 224))
        self.assertTrue(writer.isOpened())
        for _ in range(12):
            writer.write(np.zeros((224, 224, 3), dtype=np.uint8))
        writer.release()
        scan = self.upload("blank.avi", path.read_bytes(), "video/x-msvideo")
        self.assertEqual(scan["status"], "completed", scan.get("error"))
        self.assertEqual(scan["verdict"], "inconclusive")
        self.assertEqual(scan["report"]["classified_frames"], 0)
        for entry in scan["report"]["timeline"]:
            self.assertTrue({"index", "time", "fake_probability", "face_count"} <= entry.keys())
            self.assertEqual(entry["fake_probability"], .5)
        response = self.client.get(f"/api/scans/{scan['id']}/media/thumbnail.jpg?token={scan['media_token']}")
        self.assertEqual(response.status_code, 200)

    def test_retention_removes_expired_session_scan(self):
        _, data = cv2.imencode(".png", np.zeros((224, 224, 3), dtype=np.uint8))
        scan = self.upload("old.png", data.tobytes(), "image/png")
        with SessionLocal() as db:
            record = db.get(ScanRecord, scan["id"])
            directory = Path(record.original_path).parent
            record.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
            db.commit()
        self.assertGreaterEqual(purge_expired_scans(), 1)
        self.assertFalse(directory.exists())
        self.assertEqual(self.client.get(f"/api/scans/{scan['id']}", headers=SESSION_A).status_code, 404)

    def test_manifest_rejects_leakage(self):
        root = TEMP_ROOT / "manifest-test"
        root.mkdir()
        rows = []
        for split in ("train", "val", "test"):
            for label in (0, 1):
                for i in range(2):
                    filename = f"{split}-{label}-{i}.png"
                    image = np.random.default_rng(len(rows)).integers(0, 255, (32, 32, 3), dtype=np.uint8)
                    cv2.imwrite(str(root / filename), image)
                    rows.append({"path": filename, "split": split, "label": label, "group": filename})
        manifest = {"source": "synthetic unit fixture", "records": rows, "genuine_manipulated_media": False}
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        load_manifest(path)
        rows[4]["group"] = rows[0]["group"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source-group leakage"):
            load_manifest(path)
        rows[4]["group"] = rows[4]["path"]
        rows[4]["path"] = rows[0]["path"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Identical decoded images"):
            load_manifest(path)

    def test_training_smoke_and_saved_metadata(self):
        root = TEMP_ROOT / "training"
        root.mkdir()
        rows = []
        for split in ("train", "val", "test"):
            for group in range(4):
                for label in (0, 1):
                    name = f"{split}-{group}-{label}.png"
                    image = np.random.default_rng(len(rows)).integers(0, 255, (64, 64, 3), dtype=np.uint8)
                    if label:
                        image = cv2.GaussianBlur(image, (11, 11), 0)
                    cv2.imwrite(str(root / name), image)
                    rows.append({"path": name, "split": split, "group": f"{split}-{group}", "label": label})
        path = root / "manifest.json"
        path.write_text(json.dumps({"source": "synthetic regression fixture only", "records": rows,
                                    "genuine_manipulated_media": False}), encoding="utf-8")
        out = root / "candidate"
        args = SimpleNamespace(manifest=str(path), out=str(out), allow_demo=False, threads=2,
                               arch="tiny", epochs=1, batch=4, no_pretrained=True, freeze_backbone=False, lr=.001)
        with self.assertRaisesRegex(ValueError, "genuine-data"):
            train(args)
        args.allow_demo = True
        train(args)
        self.assertTrue((out / "model.pth").exists())
        metadata = json.loads((out / "model_meta.json").read_text())
        self.assertFalse(metadata["independent_evaluation"])
        self.assertEqual(metadata["test_samples"], 8)
        self.assertIn("roc_auc", metadata["test_metrics"])


if __name__ == "__main__":
    try:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProductTests))
    finally:
        _pool.shutdown(wait=True)
        engine.dispose()
        TEMP.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
