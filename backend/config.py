# backend/config.py
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseSettings, EmailStr, Field, validator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .constants import CORS_ALLOW_ORIGINS


class Settings(BaseSettings):
    # --- Database ---
    # Always use the file that actually has your tables: backend/hoa_dev.db
    frontend_url: AnyHttpUrl = Field("http://localhost:5174", env="FRONTEND_URL")
    api_base_url: AnyHttpUrl = Field("http://localhost:8000", env="API_BASE")

    database_url: str = Field("sqlite:///backend/hoa_dev.db", env="DATABASE_URL")

    # --- Security / JWT ---
    jwt_secret: str = Field("dev-secret-please-change", env="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(60 * 24 * 30, env="REFRESH_TOKEN_EXPIRE_MINUTES")

    # --- Email / Providers ---
    # Note: keep SMTP + SendGrid knobs here so env overrides are consistent across hosts.
    email_backend: str = Field("local", env="EMAIL_BACKEND")
    sendgrid_api_key: Optional[str] = Field(None, env="SENDGRID_API_KEY")
    email_host: Optional[str] = Field(None, env="EMAIL_HOST")
    email_port: int = Field(587, env="EMAIL_PORT")
    email_host_user: Optional[str] = Field(None, env="EMAIL_HOST_USER")
    email_host_password: Optional[str] = Field(None, env="EMAIL_HOST_PASSWORD")
    email_use_tls: bool = Field(True, env="EMAIL_USE_TLS")
    email_reply_to: Optional[EmailStr] = Field(None, env="EMAIL_REPLY_TO")
    email_from_address: Optional[EmailStr] = Field("admin@libertyplacehoa.com", env="EMAIL_FROM_ADDRESS")
    email_from_name: str = Field("Liberty Place HOA", env="EMAIL_FROM_NAME")
    admin_token: Optional[str] = Field(None, env="ADMIN_TOKEN")
    stripe_api_key: Optional[str] = Field(None, env="STRIPE_API_KEY")
    stripe_webhook_secret: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # --- Upload Locations ---
    uploads_dir: str = Field("uploads", env="UPLOADS_DIR")
    uploads_public_url: str = Field("uploads", env="UPLOADS_PUBLIC_URL")
    file_storage_backend: str = Field("local", env="FILE_STORAGE_BACKEND")
    s3_bucket: Optional[str] = Field(None, env="S3_BUCKET")
    s3_region: Optional[str] = Field(None, env="S3_REGION")
    s3_endpoint_url: Optional[str] = Field(None, env="S3_ENDPOINT_URL")
    s3_access_key: Optional[str] = Field(None, env="S3_ACCESS_KEY_ID")
    s3_secret_key: Optional[str] = Field(None, env="S3_SECRET_ACCESS_KEY")
    s3_public_url: Optional[str] = Field(None, env="S3_PUBLIC_URL")

    # --- File outputs / generated artifacts ---
    email_output_dir: str = Field(default="uploads/emails", env="EMAIL_OUTPUT_DIR")
    pdf_output_dir: str = Field(default="uploads/pdfs", env="PDF_OUTPUT_DIR")

    # --- CORS ---
    additional_cors_origins: Optional[str] = Field(None, env="ADDITIONAL_CORS_ORIGINS")

    # --- HTTP Security ---
    enable_hsts: bool = Field(True, env="ENABLE_HSTS")
    additional_trusted_hosts: Optional[str] = Field(None, env="ADDITIONAL_TRUSTED_HOSTS")

    # --- Click2Mail ---
    click2mail_enabled: bool = Field(False, env="CLICK2MAIL_ENABLED")
    click2mail_subdomain: str = Field("rest", env="CLICK2MAIL_SUBDOMAIN")
    click2mail_username: Optional[str] = Field(None, env="CLICK2MAIL_USERNAME")
    click2mail_password: Optional[str] = Field(None, env="CLICK2MAIL_PASSWORD")
    click2mail_return_name: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_NAME")
    click2mail_return_company: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_COMPANY")
    click2mail_return_address1: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_ADDRESS1")
    click2mail_return_address2: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_ADDRESS2")
    click2mail_return_city: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_CITY")
    click2mail_return_state: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_STATE")
    click2mail_return_postal: Optional[str] = Field(None, env="CLICK2MAIL_RETURN_POSTAL")
    click2mail_return_country: str = Field("US", env="CLICK2MAIL_RETURN_COUNTRY")
    click2mail_default_city: Optional[str] = Field(None, env="CLICK2MAIL_DEFAULT_CITY")
    click2mail_default_state: Optional[str] = Field(None, env="CLICK2MAIL_DEFAULT_STATE")
    click2mail_default_postal: Optional[str] = Field(None, env="CLICK2MAIL_DEFAULT_POSTAL")

    # --- Certified Mail ---
    certified_mail_enabled: bool = Field(False, env="CERTIFIED_MAIL_ENABLED")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @validator("database_url", pre=True)
    def normalize_database_url(cls, value: str) -> str:
        # Neon/Render sometimes supply values like: psql 'postgresql://...'
        if not isinstance(value, str):
            return value
        normalized = value.strip().strip("'\"")
        if normalized.startswith("psql "):
            normalized = normalized[5:].strip()
        # Strip wrapping quotes repeatedly to handle extra layers
        while (normalized.startswith("'") and normalized.endswith("'")) or (
            normalized.startswith('"') and normalized.endswith('"')
        ):
            normalized = normalized[1:-1].strip()
        normalized = normalized.strip("'\"")
        return normalized

    @property
    def cors_allow_origins(self) -> List[str]:
        origins: List[str] = [str(self.frontend_url)]
        for default_origin in CORS_ALLOW_ORIGINS:
            if default_origin not in origins:
                origins.append(default_origin)
        if self.additional_cors_origins:
            extras = [origin.strip() for origin in self.additional_cors_origins.split(",") if origin.strip()]
            origins.extend(extras)
        # Remove duplicates while preserving order
        seen = set()
        unique_origins: List[str] = []
        for origin in origins:
            if origin not in seen:
                unique_origins.append(origin)
                seen.add(origin)
        return unique_origins

    @property
    def uploads_root_path(self) -> Path:
        return Path(self.uploads_dir).resolve()

    @property
    def uploads_public_prefix(self) -> str:
        prefix = self.uploads_public_url.strip().lstrip("/")
        return prefix or "uploads"

    @property
    def trusted_hosts(self) -> List[str]:
        hosts: List[str] = []

        def _append_host(url_value: AnyHttpUrl | str | None) -> None:
            if not url_value:
                return
            host = getattr(url_value, "host", None) or urlsplit(str(url_value)).hostname
            if host and host not in hosts:
                hosts.append(host)

        def _append_wildcard(host: str) -> None:
            labels = host.split(".")
            if len(labels) < 3:
                return
            apex = ".".join(labels[-2:])
            wildcard = f"*.{apex}"
            if wildcard not in hosts:
                hosts.append(wildcard)

        _append_host(self.frontend_url)
        _append_host(self.api_base_url)

        for cors_origin in CORS_ALLOW_ORIGINS:
            _append_host(cors_origin)
        # If we have one subdomain of the apex (e.g., app.libertyplacehoa.com),
        # also trust sibling subdomains (e.g., api.libertyplacehoa.com) so host
        # header checks do not break when env vars drift.
        for existing in list(hosts):
            _append_wildcard(existing)

        for default_host in ("localhost", "127.0.0.1", "testserver"):
            if default_host not in hosts:
                hosts.append(default_host)

        if self.additional_trusted_hosts:
            extras = [host.strip() for host in self.additional_trusted_hosts.split(",") if host.strip()]
            for host in extras:
                if host not in hosts:
                    hosts.append(host)

        return hosts

    @property
    def click2mail_is_configured(self) -> bool:
        return (
            self.click2mail_enabled
            and bool(self.click2mail_username)
            and bool(self.click2mail_password)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Ensure path directory exists (for SQLite/local artifacts)
if settings.database_url.startswith("sqlite"):
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
