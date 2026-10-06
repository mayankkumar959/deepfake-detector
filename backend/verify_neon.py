"""Explicit live Neon regression; creates/deletes only its own test records.

Run from backend: python verify_neon.py --live
Reads DATABASE_URL from local settings. Never prints the connection string.
"""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live', action='store_true', required=True)
parser.parse_args()
temp = tempfile.TemporaryDirectory(prefix='fortexa-neon-test-')
os.environ.update(APP_ENV='test', UPLOAD_DIR=str(Path(temp.name) / 'uploads'),
                  ADMIN_PASSWORD='', CELERY_BROKER_URL='', PYTHONDONTWRITEBYTECODE='1')
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.database import engine, SessionLocal
from app.main import app
from app.models import ScanRecord, User
from app.services.celery_app import _pool

assert engine.dialect.name == 'postgresql', 'This check requires PostgreSQL, not SQLite'
session_key = secrets.token_hex(32)
owner_email = 'session-' + hashlib.sha256(session_key.encode()).hexdigest() + '@fortexa.local'
headers = {'X-Scan-Session': session_key}
other = {'X-Scan-Session': secrets.token_hex(32)}

try:
    with engine.connect() as connection:
        assert connection.connection.driver_connection.pgconn.ssl_in_use, 'Client connection must use TLS'
    with TestClient(app) as client:
        health = client.get('/api/health').json()
        assert health['status'] == 'ok' and health['database'] == 'connected'
        assert health['database_backend'] == 'postgresql'
        fixture = Path(__file__).parent / 'data/general-ai-fixtures/ai-0.jpg'
        response = client.post('/api/scans', headers=headers,
                               files={'file': ('neon-regression.jpg', fixture.read_bytes(), 'image/jpeg')})
        assert response.status_code == 201, 'Upload failed'
        scan_id = response.json()['id']
        for _ in range(600):
            response = client.get('/api/scans/' + scan_id, headers=headers)
            assert response.status_code == 200
            scan = response.json()
            if scan['status'] in ('completed', 'failed'):
                break
            time.sleep(.1)
        assert scan['status'] == 'completed', 'Scan processing failed or timed out'
        assert scan['verdict'] == 'fake' and isinstance(scan['report'], dict)
        with engine.connect() as connection:
            kind = connection.execute(text('SELECT jsonb_typeof(report) FROM scans WHERE id=:id'), {'id': scan_id}).scalar()
            assert kind == 'object', 'Report must be stored as a native JSONB object'
        assert client.get('/api/scans/' + scan_id, headers=other).status_code == 404
        media = f"/api/scans/{scan_id}/media/original?token={scan['media_token']}"
        assert client.get(media).status_code == 200
        history = client.get('/api/scans', headers=headers).json()
        assert any(item['id'] == scan_id for item in history['items'])
        assert client.delete('/api/scans/' + scan_id, headers=headers).status_code == 204
        assert client.get('/api/scans/' + scan_id, headers=headers).status_code == 404
        print('PASS: Neon TLS, application startup, AI upload/inference, JSONB save/read, private media/history and deletion.')
finally:
    _pool.shutdown(wait=True)
    with SessionLocal() as db:
        # Restrict cleanup to the cryptographically random session created above.
        user = db.query(User).filter(User.email == owner_email).first()
        if user:
            for scan in db.query(ScanRecord).filter(ScanRecord.user_id == user.id).all():
                db.delete(scan)
            db.flush()
            db.delete(user)
            db.commit()
    engine.dispose()
    temp.cleanup()
