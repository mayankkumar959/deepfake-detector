"""Delete expired completed/failed session scans; leave legacy scans untouched."""
from datetime import datetime, timedelta, timezone
from ..config import get_settings
from ..database import SessionLocal
from ..models import ScanRecord, User
from .storage import delete_scan_files


def purge_expired_scans():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=get_settings().RETENTION_HOURS)
    with SessionLocal() as db:
        expired = db.query(ScanRecord).join(User).filter(
            User.email.like("session-%@fortexa.local"),
            ScanRecord.status.in_(["completed", "failed"]),
            ScanRecord.created_at < cutoff,
        ).all()
        for scan in expired:
            delete_scan_files(scan.user_id, scan.id)
            db.delete(scan)
        db.commit()
        return len(expired)
