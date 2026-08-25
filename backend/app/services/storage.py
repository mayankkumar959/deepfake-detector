"""Storage helpers for uploaded media and generated artifacts."""
import shutil
from pathlib import Path

from ..config import get_settings

settings = get_settings()


def ensure_dirs():
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.runs_dir.mkdir(parents=True, exist_ok=True)


def scan_dir(user_id: str, scan_id: str) -> Path:
    """Return the directory for a given scan."""
    d = settings.upload_dir / user_id / scan_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(user_id: str, scan_id: str, original_name: str, data: bytes) -> Path:
    """Save uploaded bytes and return the file path."""
    d = scan_dir(user_id, scan_id)
    safe_name = Path(original_name).name  # strip path
    path = d / f"original{safe_name}"
    path.write_bytes(data)
    return path


def save_artifact(user_id: str, scan_id: str, name: str, data: bytes) -> Path:
    d = scan_dir(user_id, scan_id)
    path = d / name
    path.write_bytes(data)
    return path


def delete_scan_files(user_id: str, scan_id: str):
    d = settings.upload_dir / user_id / scan_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)