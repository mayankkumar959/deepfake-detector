"""Scan upload, listing, details, and media serving."""
import json
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import ScanRecord, User
from ..schemas import ScanListResponse, ScanResponse, ScanUploadResponse
from ..config import get_settings
from ..services import storage
from ..services.celery_app import enqueue_scan
from ..services.scan_access import session_owner, media_token, check_media_token

router = APIRouter(prefix="/scans", tags=["scans"])
settings = get_settings()

ALLOWED_IMAGE = settings.ALLOWED_IMAGE_EXT
ALLOWED_VIDEO = settings.ALLOWED_VIDEO_EXT
MAX_SIZE = settings.MAX_UPLOAD_MB * 1024 * 1024

PUBLIC_EMAIL = "public@fortexa.local"


def _get_public_user(db: Session, owner: str, create: bool = True) -> User | None:
    """Return (or create) the shared anonymous user for public scans."""
    email = f"session-{owner}@fortexa.local"
    user = db.query(User).filter(User.email == email).first()
    if user is None and not create:
        return None
    if user is None:
        user = User(
            email=email,
            username=f"session-{owner}",
            full_name="Public Visitor",
            hashed_password="-",
            role="user",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.email == email).one()
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
        media_token=media_token(scan),
    )


@router.post("", response_model=ScanUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    owner: str = Depends(session_owner),
):
    """Upload a photo or video for deepfake analysis."""
    if not file.filename or not file.filename.strip():
        raise HTTPException(400, "No filename provided")
    active = db.query(ScanRecord).filter(ScanRecord.status.in_(["pending", "processing"])).count()
    if active >= 16:
        raise HTTPException(429, "The scan queue is full. Please try again shortly.")

    ext = Path(file.filename).suffix.lower()
    if ext in ALLOWED_IMAGE:
        media_type = "image"
    elif ext in ALLOWED_VIDEO:
        media_type = "video"
    else:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: "
                                   f"{' '.join(ALLOWED_IMAGE + ALLOWED_VIDEO)}")

    chunks = []
    size = 0
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_SIZE:
            raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_MB} MB)")
        chunks.append(chunk)
    contents = b"".join(chunks)
    if not contents:
        raise HTTPException(400, "The uploaded file is empty")
    if media_type == "image":
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(contents)) as image:
                if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "Image resolution exceeds the processing limit")
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(400, "The file is not a readable image")

    user = _get_public_user(db, owner)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    if len(safe_filename) > 200:
        raise HTTPException(400, "Filename is too long")

    # Create DB record (original_path filled in after saving the file)
    scan = ScanRecord(
        user_id=user.id,
        filename=safe_filename,
        original_path="",
        media_type=media_type,
        file_size=len(contents),
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Save file to disk
    saved_path = storage.save_upload(user.id, scan.id, safe_filename, contents)
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
    owner: str = Depends(session_owner),
):
    public_user = _get_public_user(db, owner, create=False)
    if public_user is None:
        return ScanListResponse(total=0, page=page, page_size=page_size, items=[])
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
    owner: str = Depends(session_owner),
):
    user = _get_public_user(db, owner, create=False)
    if user is None:
        raise HTTPException(404, "Scan not found")
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
        ScanRecord.user_id == user.id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")
    include_report = scan.status == "completed"
    return _scan_to_response(scan, include_report=include_report)


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    owner: str = Depends(session_owner),
):
    public_user = _get_public_user(db, owner, create=False)
    if public_user is None:
        raise HTTPException(404, "Scan not found")
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
        ScanRecord.user_id == public_user.id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")
    if scan.status in ("pending", "processing"):
        raise HTTPException(409, "Wait for processing to finish before deleting this scan")

    storage.delete_scan_files(public_user.id, scan_id)
    db.delete(scan)
    db.commit()
    return None


@router.get("/{scan_id}/media/{filename}")
def serve_media(
    scan_id: str,
    filename: str,
    db: Session = Depends(get_db),
    token: str | None = Query(None),
):
    """Serve original uploads and generated artifacts (heatmaps, thumbnails)."""
    scan = db.query(ScanRecord).filter(
        ScanRecord.id == scan_id,
    ).first()
    if scan is None:
        raise HTTPException(404, "Scan not found")
    check_media_token(scan, token)
    if filename not in {"original", scan.filename, "heatmap.jpg", "thumbnail.jpg", "report.json"}:
        raise HTTPException(404, "File not found")

    scan_dir = storage.scan_dir(scan.user_id, scan_id)
    is_original = filename == "original" or (filename == scan.filename and filename not in {"heatmap.jpg", "thumbnail.jpg", "report.json"})
    candidates = [scan_dir / f"original{scan.filename}"] if is_original else [scan_dir / filename]
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
    return FileResponse(str(file_path), media_type=mime, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})
