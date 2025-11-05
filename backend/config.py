# backend/config.py
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AnyHttpUrl, BaseSettings, EmailStr
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
    refresh_token_expire_minutes: int = 60 * 24 * 30  # 30 days

    # --- CORS ---
    cors_origins: List[AnyHttpUrl] = ["http://localhost:5173", "http://localhost:5174"]  # type: ignore[assignment]
    # --- Email ---
    email_backend: str = "local"
    sendgrid_api_key: str | None = None
    email_from_address: EmailStr | None = None
    email_from_name: str = "Liberty Place HOA"
    email_output_dir: str = "uploads/emails"

    # --- Document Generation ---
    pdf_output_dir: str = "uploads/pdfs"

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

pdf_output_path = Path(settings.pdf_output_dir)
pdf_output_path.mkdir(parents=True, exist_ok=True)

email_output_path = Path(settings.email_output_dir)
email_output_path.mkdir(parents=True, exist_ok=True)

# --- SQLAlchemy setup ---
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
