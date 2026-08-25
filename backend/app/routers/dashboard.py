from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ScanRecord, User
from ..schemas import DashboardSummary, ScanResponse, TrendPoint
from ..deps import get_current_user
from ..ml.engine import get_ml_status

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _scan_to_schema(scan: ScanRecord) -> ScanResponse:
    return ScanResponse.model_validate(scan)


@router.get("/summary", response_model=DashboardSummary)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = db.query(ScanRecord).filter(ScanRecord.user_id == user.id)

    total = base.count()
    fake = base.filter(ScanRecord.verdict == "fake").count()
    real = base.filter(ScanRecord.verdict == "real").count()
    inconclusive = base.filter(ScanRecord.verdict == "inconclusive").count()
    images = base.filter(ScanRecord.media_type == "image").count()
    videos = base.filter(ScanRecord.media_type == "video").count()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today = base.filter(ScanRecord.created_at >= today_start).count()

    recent = (
        base.order_by(ScanRecord.created_at.desc()).limit(8).all()
    )

    return DashboardSummary(
        total_scans=total,
        fake_detected=fake,
        real_detected=real,
        inconclusive=inconclusive,
        images_analyzed=images,
        videos_analyzed=videos,
        today_scans=today,
        model_status=get_ml_status()["status"],
        recent_scans=[_scan_to_schema(s) for s in recent],
    )


@router.get("/trends", response_model=list[TrendPoint])
def trends(
    days: int = 7,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    days = max(1, min(days, 30))
    points: list[TrendPoint] = []
    now = datetime.now(timezone.utc)
    for i in range(days - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        base = db.query(ScanRecord).filter(
            ScanRecord.user_id == user.id,
            ScanRecord.created_at >= day_start,
            ScanRecord.created_at < day_end,
        )
        total = base.count()
        fake = base.filter(ScanRecord.verdict == "fake").count()
        real = base.filter(ScanRecord.verdict == "real").count()

        points.append(TrendPoint(date=day_start.strftime("%Y-%m-%d"), total=total, fake=fake, real=real))

    return points