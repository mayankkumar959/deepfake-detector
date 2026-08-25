"""Admin-only endpoints for user management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, ScanRecord
from ..schemas import AdminUserUpdate, UserResponse
from ..deps import get_current_user, require_admin
from ..deps import get_current_user as require_auth

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def list_users(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(404, "User not found")
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = 1 if payload.is_active else 0
    db.commit()
    db.refresh(target)
    return UserResponse.model_validate(target)


@router.get("/stats")
def admin_stats(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(User).count()
    total_scans = db.query(ScanRecord).count()
    fake = db.query(ScanRecord).filter(ScanRecord.verdict == "fake").count()
    real = db.query(ScanRecord).filter(ScanRecord.verdict == "real").count()
    failed = db.query(ScanRecord).filter(ScanRecord.status == "failed").count()
    return {
        "total_users": total_users,
        "total_scans": total_scans,
        "fake_detected": fake,
        "real_detected": real,
        "inconclusive": total_scans - fake - real,
        "failed_scans": failed,
    }