"""Optional Celery integration.

If Redis + Celery are installed and configured (CELERY_BROKER_URL set), scans
are processed by the worker. Otherwise the app transparently falls back to an
inline thread pool so everything works with zero extra services.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..config import get_settings

settings = get_settings()

# Try to create a Celery app; None if unavailable/not configured
celery_app = None
try:
    if settings.CELERY_BROKER_URL and settings.CELERY_BROKER_URL.startswith("redis"):
        from celery import Celery  # noqa
        celery_app = Celery(
            "fortexa",
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND or settings.CELERY_BROKER_URL,
        )
        celery_app.conf.update(task_serializer="json", result_serializer="json", timezone="UTC")
except Exception:
    celery_app = None

# Inline thread pool (used when Celery is unavailable)
_pool = ThreadPoolExecutor(max_workers=4)


def enqueue_scan(scan_id: str) -> str:
    """Submit a scan for processing. Returns the execution backend name."""
    if celery_app is not None:
        try:
            from ..tasks.scan_tasks import process_scan_task
            process_scan_task.delay(scan_id)
            return "celery"
        except Exception:
            pass

    _pool.submit(_run_inline, scan_id)
    return "inline-thread"


def _run_inline(scan_id: str):
    from .detector import process_scan
    process_scan(scan_id)