from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from ..security import create_access_token, hash_password, verify_password
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    username = payload.username.strip()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    # First user ever becomes admin (bootstrap)
    is_first = db.query(User).count() == 0
    user = User(
        email=email,
        username=username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="admin" if is_first else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserResponse)
def update_profile(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.username is not None and payload.username.strip() != user.username:
        exists = db.query(User).filter(User.username == payload.username.strip()).first()
        if exists:
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = payload.username.strip()
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


# ── Google OAuth (optional) ───────────────────────────────────────
# Enabled only when GOOGLE_CLIENT_ID is configured in .env

from ..config import get_settings  # noqa: E402

_settings = get_settings()


@router.get("/oauth/google")
def oauth_google_start():
    """Start the Google OAuth flow. Requires GOOGLE_CLIENT_ID to be set."""
    if not _settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured")
    params = (
        f"client_id={_settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={_settings.OAUTH_REDIRECT_URI}"
        f"&response_type=code&scope=openid%20email%20profile"
        f"&access_type=online"
    )
    return {"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}