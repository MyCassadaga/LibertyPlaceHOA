# backend/config.py
from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic import AnyHttpUrl, BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


class Settings(BaseSettings):
    # --- Database ---
    # Always use the file that actually has your tables: backend/hoa_dev.db
    database_url: str = "sqlite:///backend/hoa_dev.db"

    # --- Security / JWT ---
    jwt_secret: str = "dev-secret-please-change"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # --- CORS ---
    cors_origins: List[AnyHttpUrl] = ["http://localhost:5173", "http://localhost:5174"]  # type: ignore[assignment]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Ensure path directory exists (for SQLite)
db_path = Path(settings.database_url.replace("sqlite:///", ""))
db_path.parent.mkdir(parents=True, exist_ok=True)

# --- SQLAlchemy setup ---
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
