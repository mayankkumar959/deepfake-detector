"""Password hashing (PBKDF2-SHA256) and JWT token creation/verification.

Uses only stdlib + PyJWT to avoid bcrypt/argon2 dependency issues on Windows.
"""
import hashlib
import os
import time
import secrets
from typing import Optional

import jwt
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()

# ── Password Hashing (PBKDF2-SHA256) ──────────────────────────────

PBKDF2_ITERATIONS = 600_000
SALT_LENGTH = 32


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256. Returns salt:hash (hex)."""
    salt = secrets.token_hex(SALT_LENGTH)
    pwd_bytes = password.encode("utf-8")
    salt_bytes = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, PBKDF2_ITERATIONS)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored salt:hash string."""
    try:
        salt, hsh = stored.split(":")
        pwd_bytes = password.encode("utf-8")
        salt_bytes = bytes.fromhex(salt)
        dk = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, PBKDF2_ITERATIONS)
        return hsh == dk.hex()
    except (ValueError, AttributeError):
        return False


# ── JWT ───────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str          # user_id
    email: str
    role: str
    iat: float
    exp: float


def create_access_token(user_id: str, email: str, role: str = "user") -> str:
    expire = time.time() + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": time.time(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload dict or None on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None