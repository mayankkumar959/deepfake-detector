"""Scan upload, listing, details, and media serving."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ScanRecord, User
from ..schemas import ScanListResponse, ScanResponse, ScanUploadResponse
from ..config import get_settings
from ..services import storage
from ..services.celery_app import enqueue_scan

router = APIRouter(prefix="/scans", tags=["scans"])
settings = get_settings()

ALLOWED_IMAGE = settings.ALLOWED_IMAGE_EXT
ALLOWED_VIDEO = settings.ALLOWED_VIDEO_EXT
MAX_SIZE = settings.MAX_UPLOAD_MB * 1024 * 1024

PUBLIC_EMAIL = "public@fortexa.local"


def _get_public_user(db: Session) -> User:
    """Return (or create) the shared anonymous user for public scans."""
    user = db.query(User).filter(User.email == PUBLIC_EMAIL).first()
    if user is None:
        user = User(
            email=PUBLIC_EMAIL,
            username="public",
            full_name="Public Visitor",
            hashed_password="-",
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _scan_to_response(scan: ScanRecord, include_report: bool = False) -> ScanResponse:
    """Convert a ScanRecord model to a Pydantic response."""
    return ScanResponse(
        id=scan.id,
        user_id=scan.user_id,
        filename=scan.filename,
        media_type=scan.media_type,
        file_size=scan.file_size,
        status=scan.status,
        verdict=scan.verdict,
        fake_probability=scan.fake_probability,
        real_probability=scan.real_probability,
        confidence=scan.confidence,
        risk_level=scan.risk_level,
        model_used=scan.model_used,
        method=scan.method,
        error=scan.error,
        duration_ms=scan.duration_ms,
        frame_count=scan.frame_count,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        report=json.loads(scan.report) if scan.report and include_report else None,
    )


@router.post("", response_model=ScanUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a photo or video for deepfake analysis."""
    if not file.filename or not file.filename.strip():
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext in ALLOWED_IMAGE:
        media_type = "image"
    elif ext in ALLOWED_VIDEO:
        media_type = "video"
    else:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: "
                                   f"{' '.join(ALLOWED_IMAGE + ALLOWED_VIDEO)}")

    contents = file.file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_MB} MB)")

    user = _get_public_user(db)

    # Create DB record (original_path filled in after saving the file)
    scan = ScanRecord(
        user_id=user.id,
        filename=file.filename,
        original_path="",
        media_type=media_type,
        file_size=len(contents),
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Save file to disk
    saved_path = storage.save_upload(user.id, scan.id, file.filename, contents)
    scan.original_path = str(saved_path)
    db.commit()

    # Enqueue background processing (Celery if configured, else inline thread)
    backend = enqueue_scan(scan.id)

    return ScanUploadResponse(
        id=scan.id,
        status="pending",
        message=f"Upload accepted. Processing via {backend}.",
    )


@router.get("", response_model=ScanListResponse)
def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    media_type: str | None = Query(None, pattern="^(image|video)$"),
    verdict: str | None = Query(None, pattern="^(fake|real|inconclusive)$"),
    db: Session = Depends(get_db),
):
    public_user = _get_public_user(db)
    base = db.query(ScanRecord).filter(ScanRecord.user_id == public_user.id)
    if media_type:
        base = base.filter(ScanRecord.media_type == media_type)
    if verdict:
        base = base.filter(ScanRecord.verdict == verdict)

    total = base.count()
    items = (
        base.order_by(desc(ScanRecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ScanListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_scan_to_response(s) for s in items],
    )


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
):
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")
    include_report = scan.status == "completed"
    return _scan_to_response(scan, include_report=include_report)


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    scan_id: str,
    db: Session = Depends(get_db),
):
    public_user = _get_public_user(db)
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
        ScanRecord.user_id == public_user.id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")

    storage.delete_scan_files(public_user.id, scan_id)
    db.delete(scan)
    db.commit()
    return None


@router.get("/{scan_id}/media/{filename}")
def serve_media(
    scan_id: str,
    filename: str,
    db: Session = Depends(get_db),
):
    """Serve original uploads and generated artifacts (heatmaps, thumbnails)."""
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")

    scan_dir = storage.scan_dir(scan.user_id, scan_id)
    candidates = [scan_dir / filename, scan_dir / f"original{Path(filename).name}"]
    file_path = next((c for c in candidates if c.exists()), None)
    if file_path is None:
        raise HTTPException(404, "File not found")

    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    ext = file_path.suffix.lower()
    mime = media_type_map.get(ext, "application/octet-stream")
    return FileResponse(str(file_path), media_type=mime)
