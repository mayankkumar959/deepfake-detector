import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import TEXT as SQLITE_TEXT

from .database import Base
from .config import get_settings

# Use a portable JSON/text type based on database dialect
settings = get_settings()
if "postgresql" in settings.DATABASE_URL:
    from sqlalchemy.dialects.postgresql import JSONB
    JSONType = JSONB
else:
    JSONType = SQLITE_TEXT  # SQLite: store as JSON string


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class User(Base):
    __tablename__ = "users"

    id = Column(String(12), primary_key=True, default=_uuid, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # "user" | "admin"
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    scans = relationship("ScanRecord", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class ScanRecord(Base):
    __tablename__ = "scans"

    id = Column(String(12), primary_key=True, default=_uuid, index=True)
    user_id = Column(String(12), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    original_path = Column(String(1000), nullable=False)
    media_type = Column(String(20), nullable=False)  # "image" | "video"
    file_size = Column(Integer, default=0)

    status = Column(String(20), default="pending")  # pending | processing | completed | failed
    verdict = Column(String(30), nullable=True)  # fake | real | inconclusive
    fake_probability = Column(Float, nullable=True)
    real_probability = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)  # high | medium | low
    model_used = Column(String(100), nullable=True)
    method = Column(String(50), nullable=True)

    # report stored as JSON text (or JSONB in postgres)
    report = Column(JSONType, nullable=True)

    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    frame_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="scans")

    def __repr__(self):
        return f"<Scan {self.id} {self.media_type} {self.status}>"