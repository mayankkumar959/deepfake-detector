from functools import lru_cache
from pathlib import Path
import secrets
from pydantic import Field, model_validator

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Fortexa"
    APP_ENV: str = "development"
    DETECTOR_TASK: str = "ai-image"
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_hex(32))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "sqlite+aiosqlite:///./fortexa.db"
    UPLOAD_DIR: str = "./uploads"
    RUNS_DIR: str = "./runs/general-ai-trained-indoor-20261005"

    REDIS_URL: str = ""
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    MAX_UPLOAD_MB: int = 200
    RETENTION_HOURS: int = 24
    MAX_VIDEO_SECONDS: int = 300
    MAX_IMAGE_PIXELS: int = 20_000_000
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/oauth/google/callback"

    ADMIN_EMAIL: str = "admin@fortexa.app"
    ADMIN_PASSWORD: str = ""

    @model_validator(mode="after")
    def validate_limits(self):
        if self.DETECTOR_TASK not in ('ai-image', 'legacy-face'):
            raise ValueError('DETECTOR_TASK must be ai-image or legacy-face')
        if min(self.MAX_UPLOAD_MB, self.RETENTION_HOURS, self.MAX_VIDEO_SECONDS, self.MAX_IMAGE_PIXELS) <= 0:
            raise ValueError("Processing and retention limits must be positive")
        if self.APP_ENV == "production" and (len(self.SECRET_KEY) < 32 or self.SECRET_KEY.startswith("change-me")):
            raise ValueError("Set a random SECRET_KEY of at least 32 characters for production")
        return self

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
