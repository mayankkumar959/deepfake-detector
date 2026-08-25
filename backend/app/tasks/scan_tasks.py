"""Celery shared tasks for background scan processing."""
from ..services.celery_app import celery_app


@celery_app.task(name="scans.process_scan", bind=True)
def process_scan_task(self, scan_id: str):
    """Celery task wrapper (only used when Celery is configured)."""
    from ..services.detector import process_scan
    try:
        process_scan(scan_id)
        return {"scan_id": scan_id, "status": "completed"}
    except Exception as exc:
        self.retry(exc=exc, countdown=2, max_retries=2)