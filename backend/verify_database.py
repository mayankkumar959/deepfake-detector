"""Offline compatibility checks; never accesses the configured Neon database."""
import json
import os
import unittest

os.environ.update(DATABASE_URL='sqlite:///:memory:', APP_ENV='test')
from app.database import Base, engine, SessionLocal, database_url
from app.models import User, ScanRecord
from app.routers.scans import _scan_to_response
from sqlalchemy.dialects import postgresql
from app.config import Settings

class DatabaseTests(unittest.TestCase):
    def test_production_requires_postgresql(self):
        with self.assertRaises(ValueError):
            Settings(_env_file=None, APP_ENV='production', SECRET_KEY='test-secret-' * 4,
                     DATABASE_URL='sqlite:///:memory:')

    def test_production_accepts_neon_url(self):
        settings = Settings(_env_file=None, APP_ENV='production', SECRET_KEY='test-secret-' * 4,
                            DATABASE_URL='postgresql://owner:example-password@host/db?sslmode=require')
        self.assertTrue(settings.DATABASE_URL.startswith('postgresql://'))

    def test_neon_url_preserves_security_parameters(self):
        for prefix in ('postgresql', 'postgres'):
            url = database_url(prefix + '://owner:example-password@host/db?sslmode=require&channel_binding=require')
            self.assertEqual(url.drivername, 'postgresql+psycopg')
            self.assertEqual(url.query['sslmode'], 'require')
            self.assertEqual(url.query['channel_binding'], 'require')
            self.assertEqual(url.password, 'example-password')

    def test_sqlite_sync_driver(self):
        self.assertEqual(database_url('sqlite+aiosqlite:///:memory:').drivername, 'sqlite')

    def test_postgresql_uses_jsonb(self):
        self.assertEqual(ScanRecord.__table__.c.report.type.compile(dialect=postgresql.dialect()), 'JSONB')

    def test_native_and_legacy_report_roundtrip(self):
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            user = User(email='test@example.test', username='database-test', hashed_password='-')
            db.add(user)
            db.flush()
            for report in ({'verdict': 'real'}, json.dumps({'verdict': 'real'})):
                scan = ScanRecord(user_id=user.id, filename='fixture.jpg', original_path='test-only', media_type='image', report=report)
                db.add(scan)
                db.commit()
                db.refresh(scan)
                self.assertEqual(_scan_to_response(scan, include_report=True).report['verdict'], 'real')
                self.assertIsNone(_scan_to_response(scan, include_report=False).report)
            db.delete(user)
            db.commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
