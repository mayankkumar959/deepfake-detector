from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Fortexa"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-fortexa-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "sqlite+aiosqlite:///./fortexa.db"
    UPLOAD_DIR: str = "./uploads"
    RUNS_DIR: str = "./runs"

    REDIS_URL: str = ""
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    MAX_UPLOAD_MB: int = 200
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/oauth/google/callback"

    ADMIN_EMAIL: str = "admin@fortexa.app"
    ADMIN_PASSWORD: str = "Admin@12345"

    ALLOWED_IMAGE_EXT: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    ALLOWED_VIDEO_EXT: tuple[str, ...] = (".mp4", ".mov", ".avi", ".mkv", ".webm")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def upload_dir(self) -> Path:
        return Path(self.UPLOAD_DIR)

    @property
    def runs_dir(self) -> Path:
        return Path(self.RUNS_DIR)


@lru_cache()
def get_settings() -> Settings:
    return Settings()