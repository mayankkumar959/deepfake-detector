"""Fortexa — Enterprise Deepfake Detection Platform.

FastAPI application entry point.
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import Base, engine, SessionLocal
from .models import User
from .security import hash_password
from .routers import auth, scans, dashboard, admin, health
from .services.storage import ensure_dirs
from .ml.engine import load_ml_engine

settings = get_settings()


def _seed_admin():
    """Create default admin if not exists."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=settings.ADMIN_EMAIL,
                username="admin",
                full_name="Fortexa Admin",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print(f"[OK] Admin seeded: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    ensure_dirs()
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    load_ml_engine()
    ml_status = __import__("app.ml.engine", fromlist=["get_ml_status"]).get_ml_status()
    print(f"[OK] Detection engine: {ml_status['status']} ({ml_status['model']})")
    yield
    # Shutdown (nothing to clean)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Enterprise Deepfake Detection Platform — Photo & Video Forensic Analysis",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────
origins = [
    settings.FRONTEND_ORIGIN,
    "http://localhost:5173",
    "http://localhost:3000",
]
if settings.APP_ENV == "production":
    origins = [settings.FRONTEND_ORIGIN]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exc_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)[:300]}"},
    )

# ── Routers ───────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(health.router, prefix="/api")


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }