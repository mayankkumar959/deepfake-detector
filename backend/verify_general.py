"""General AI-image regression on disposable data, not an accuracy certification."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent
TEMP = tempfile.TemporaryDirectory(prefix='fortexa-general-test-')
os.environ.update(DETECTOR_TASK='ai-image', APP_ENV='test', DATABASE_URL='sqlite:///' + str(Path(TEMP.name) / 'test.db'),
                  UPLOAD_DIR=str(Path(TEMP.name) / 'uploads'), SECRET_KEY='isolated-test-secret-' * 4,
                  ADMIN_PASSWORD='', CELERY_BROKER_URL='', PYTHONDONTWRITEBYTECODE='1')
import cv2
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine
from app.ml.general_image import load_general_detector, analyze_general_frame
from app.services.celery_app import _pool
from app.services.report import verdict_for

HEADERS = {'X-Scan-Session': 'a' * 64}
OTHER = {'X-Scan-Session': 'b' * 64}


class GeneralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def upload(self, image, name='fixture.jpg'):
        ok, data = cv2.imencode('.jpg', image)
        self.assertTrue(ok)
        response = self.client.post('/api/scans', headers=HEADERS, files={'file': (name, data.tobytes(), 'image/jpeg')})
        self.assertEqual(response.status_code, 201, response.text)
        scan_id = response.json()['id']
        for _ in range(400):
            response = self.client.get('/api/scans/' + scan_id, headers=HEADERS)
            self.assertEqual(response.status_code, 200)
            scan = response.json()
            if scan['status'] in ('completed', 'failed'):
                self.assertEqual(scan['status'], 'completed', scan.get('error'))
                return scan
            time.sleep(.1)
        self.fail('General image inference timed out')

    def test_health_is_general_not_face(self):
        health = self.client.get('/api/health').json()
        self.assertEqual(health['status'], 'ok')
        self.assertEqual(health['detection_engine']['status'], 'ml-ai-image-classifier')
        self.assertTrue(health['detection_engine']['test_metrics']['samples'] > 0)

    def test_blank_is_inconclusive(self):
        scan = self.upload(np.zeros((256, 256, 3), dtype=np.uint8), 'blank.jpg')
        self.assertEqual(scan['verdict'], 'inconclusive')
        self.assertIsNone(scan['report']['ml_probability'])

    def test_small_image_is_inconclusive(self):
        image = np.random.default_rng(42).integers(0, 256, (64, 64, 3), dtype=np.uint8)
        self.assertEqual(self.upload(image)['verdict'], 'inconclusive')

    def test_actual_generated_and_real_images_through_api(self):
        records = []
        model = load_general_detector()
        for label, prefix in ((0, 'real'), (1, 'ai')):
            for index in range(5):
                image = cv2.imread(str(ROOT / f'data/general-ai-fixtures/{prefix}-{index}.jpg'))
                self.assertIsNotNone(image, 'Genuine general-image fixtures required')
                for quality in (95, 60):
                    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                    analysis = analyze_general_frame(decoded)
                    score = analysis['ml_probability']
                    if score is not None:
                        self.assertEqual(verdict_for(score), 'fake' if label else 'real',
                                         f'Ground-truth regression failed: {prefix}-{index}, JPEG {quality}, score {score}')
                    records.append({'fixture': f'{prefix}-{index}', 'ground_truth': label, 'jpeg_quality': quality,
                                    'ai_score': score, 'verdict': verdict_for(score) if score is not None else 'inconclusive'})
                # API re-encodes with OpenCV default quality: compare the same bytes.
                ok, encoded = cv2.imencode('.jpg', image)
                decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                scan = self.upload(image, f'{prefix}-{index}.jpg')
                if min(decoded.shape[:2]) >= 224 and float(decoded.std()) >= 2:
                    self.assertEqual(scan['method'], 'ml-ai-image-classifier')
                    self.assertAlmostEqual(scan['fake_probability'], model.predict_prob(decoded), places=3)
                self.assertIsNone(scan['confidence'])
                self.assertEqual(self.client.get('/api/scans/' + scan['id'], headers=OTHER).status_code, 404)
                self.assertEqual(self.client.get('/api/scans/' + scan['id'] + '/media/original').status_code, 404)
                url = f"/api/scans/{scan['id']}/media/original?token={scan['media_token']}"
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.delete('/api/scans/' + scan['id'], headers=HEADERS).status_code, 204)
                print(json.dumps({'checked_fixture': f'{prefix}-{index}', 'api_score': scan['fake_probability'], 'method': scan['method']}), flush=True)
        output = {'scope': '10 small fixtures, two JPEG variants each; integration evidence only, not an accuracy claim', 'records': records}
        from app.config import get_settings
        (get_settings().runs_dir / 'integration_evaluation.json').write_text(json.dumps(output, indent=2))
        print(json.dumps(output), flush=True)

    def test_camera_photo_compression_keeps_real_label(self):
        path = os.environ.get('CAMERA_REGRESSION_IMAGE')
        if not path:
            self.skipTest('Set CAMERA_REGRESSION_IMAGE to a known real camera photo; no user uploads are read implicitly')
        image = cv2.imread(path)
        self.assertIsNotNone(image)
        records = []
        for quality in (95, 60, 40):
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            self.assertTrue(ok)
            decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            analysis = analyze_general_frame(decoded)
            self.assertIsNotNone(analysis['ml_probability'])
            self.assertEqual(verdict_for(analysis['ml_probability']), 'real')
            records.append({'jpeg_quality': quality, 'ai_score': analysis['ml_probability']})
        self.assertEqual(self.upload(image, 'real-camera.jpg')['verdict'], 'real')
        from app.config import get_settings
        (get_settings().runs_dir / 'camera_regression.json').write_text(json.dumps({
            'scope': 'Single user camera photo, not used in training. JPEG recompression is not WhatsApp emulation.',
            'records': records}, indent=2))

    def test_missing_general_model_is_inconclusive(self):
        from unittest.mock import patch
        image = cv2.imread(str(ROOT / 'data/general-ai-fixtures/ai-0.jpg'))
        with patch('app.ml.general_image.load_general_detector', return_value=None):
            result = analyze_general_frame(image)
        self.assertIsNone(result['ml_probability'])
        self.assertEqual(result['fake_probability'], .5)


if __name__ == '__main__':
    (ROOT / '.runtime-check').mkdir(exist_ok=True)
    cv2.imwrite(str(ROOT / '.runtime-check/blank.png'), np.zeros((256, 256, 3), dtype=np.uint8))
    try:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GeneralTests))
    finally:
        _pool.shutdown(wait=True)
        engine.dispose()
        TEMP.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
