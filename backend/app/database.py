from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

def database_url(value: str):
    """Use the installed synchronous driver for SQLite and PostgreSQL DSNs."""
    url = make_url(value)
    if url.drivername in ('postgres', 'postgresql'):
        return url.set(drivername='postgresql+psycopg')
    if url.drivername == 'sqlite+aiosqlite':
        return url.set(drivername='sqlite')
    return url


url = database_url(settings.DATABASE_URL)
if url.get_backend_name() == 'sqlite':
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        hide_parameters=True,
    )
else:
    engine = create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={'connect_timeout': 15, 'prepare_threshold': None}
        if url.drivername == 'postgresql+psycopg' else {},
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
