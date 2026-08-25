from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..ml.engine import get_ml_status

router = APIRouter(prefix="/health", tags=["health"])

settings = get_settings()


@router.get("")
def health(db: Session = Depends(get_db)):
    # DB check
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    ml_status = get_ml_status()

    celery_ok = False
    try:
        import redis  # noqa
        from ..services.celery_app import celery_app
        celery_ok = celery_app is not None
    except Exception:
        celery_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "database": "connected" if db_ok else "error",
        "detection_engine": ml_status,
        "background_worker": "celery" if celery_ok else "inline-thread",
        "environment": settings.APP_ENV,
    }