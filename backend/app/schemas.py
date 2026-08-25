from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


# ── User ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None


# ── Scan ──────────────────────────────────────────────────────────

class ScanResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    media_type: str
    file_size: int
    status: str
    verdict: Optional[str] = None
    fake_probability: Optional[float] = None
    real_probability: Optional[float] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    model_used: Optional[str] = None
    method: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    frame_count: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Full report (only included in detail endpoint)
    report: Optional[Any] = None

    model_config = {"from_attributes": True}


class ScanListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ScanResponse]


class ScanUploadResponse(BaseModel):
    id: str
    status: str
    message: str


# ── Dashboard ─────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_scans: int
    fake_detected: int
    real_detected: int
    inconclusive: int
    images_analyzed: int
    videos_analyzed: int
    today_scans: int
    model_status: str
    recent_scans: list[ScanResponse]


class TrendPoint(BaseModel):
    date: str
    total: int
    fake: int
    real: int


# ── Admin ─────────────────────────────────────────────────────────

class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


# Resolve forward references (TokenResponse references UserResponse, defined above).
TokenResponse.model_rebuild()