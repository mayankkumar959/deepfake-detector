import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

# Use aiosqlite for async if SQLite, else create sync engine
# For simplicity we use sync engine with SQLite fallback
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://"),
        connect_args={"check_same_thread": False},
        echo=settings.APP_ENV == "development",
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "development",
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()