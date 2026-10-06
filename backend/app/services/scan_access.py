"""Per-browser anonymous ownership; media access is scoped to one scan."""
import hashlib
import hmac
import re
from fastapi import Header, HTTPException
from ..config import get_settings


def session_owner(x_scan_session: str | None = Header(default=None)) -> str:
    if not x_scan_session or not re.fullmatch(r"[a-f0-9]{64}", x_scan_session):
        raise HTTPException(401, "A browser scan session is required.")
    return hashlib.sha256(x_scan_session.encode()).hexdigest()


def media_token(scan) -> str:
    return hmac.new(get_settings().SECRET_KEY.encode(),
                    f"media:{scan.id}:{scan.user_id}".encode(), hashlib.sha256).hexdigest()


def check_media_token(scan, token: str | None):
    if not token or not hmac.compare_digest(token, media_token(scan)):
        raise HTTPException(404, "Media not found")
