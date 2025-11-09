from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from ..config import settings


class StorageBackend(str, Enum):
    LOCAL = "local"
    S3 = "s3"


@dataclass
class StoredFile:
    relative_path: str
    public_path: str
    local_path: Optional[str] = None


@dataclass
class RetrievedFile:
    content: bytes
    content_type: str


class StorageService:
    def __init__(self) -> None:
        backend_name = (settings.file_storage_backend or "local").lower()
        if backend_name not in StorageBackend.__members__:
            backend_name = "local"
        self.backend = StorageBackend[backend_name.upper()]
        self.upload_root = settings.uploads_root_path
        self.public_prefix = settings.uploads_public_prefix.strip("/")
        self.api_base = settings.api_base_url.rstrip("/")
        self._s3_client = None
        if self.backend == StorageBackend.LOCAL:
            self.upload_root.mkdir(parents=True, exist_ok=True)
        else:
            self._configure_s3_client()

    def _configure_s3_client(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("boto3 is required for S3 storage backend.") from exc

        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET must be set when using the S3 storage backend.")

        session_kwargs = {
            "region_name": settings.s3_region,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
        }
        if settings.s3_endpoint_url:
            session_kwargs["endpoint_url"] = settings.s3_endpoint_url
        self._s3_client = boto3.client("s3", **{k: v for k, v in session_kwargs.items() if v})

    def _normalize_relative(self, relative_path: str) -> str:
        relative = relative_path.strip().lstrip("/")
        if relative.startswith(self.public_prefix + "/"):
            relative = relative.split("/", 1)[1]
        return relative

    def _build_public_path(self, relative_path: str) -> str:
        if self.public_prefix.startswith("http"):
            base = self.public_prefix.rstrip("/")
            return f"{base}/{relative_path}"
        return f"{self.public_prefix}/{relative_path}".lstrip("/")

    def save_file(self, relative_path: str, content: bytes, content_type: Optional[str] = None) -> StoredFile:
        relative = self._normalize_relative(relative_path)
        guessed_type = content_type or mimetypes.guess_type(relative)[0] or "application/octet-stream"
        public_path = self._build_public_path(relative)

        if self.backend == StorageBackend.LOCAL:
            target_path = self.upload_root / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
            return StoredFile(relative_path=relative, public_path=public_path, local_path=str(target_path))

        assert self._s3_client is not None  # for type checkers
        extra_args = {"ContentType": guessed_type}
        self._s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=relative,
            Body=content,
            **extra_args,
        )
        return StoredFile(relative_path=relative, public_path=public_path, local_path=None)

    def delete_file(self, relative_or_public_path: str) -> None:
        relative = self._normalize_relative(relative_or_public_path)
        if not relative:
            return
        if self.backend == StorageBackend.LOCAL:
            target = self.upload_root / relative
            if target.exists():
                target.unlink()
            return

        assert self._s3_client is not None
        self._s3_client.delete_object(Bucket=settings.s3_bucket, Key=relative)

    def retrieve_file(self, relative_or_public_path: str) -> RetrievedFile:
        relative = self._normalize_relative(relative_or_public_path)
        if self.backend == StorageBackend.LOCAL:
            target = self.upload_root / relative
            if not target.exists():
                raise HTTPException(status_code=404, detail="File not found.")
            data = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return RetrievedFile(content=data, content_type=content_type)

        assert self._s3_client is not None
        try:
            obj = self._s3_client.get_object(Bucket=settings.s3_bucket, Key=relative)
        except self._s3_client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
            raise HTTPException(status_code=404, detail="File not found.") from None
        content = obj["Body"].read()
        content_type = obj.get("ContentType") or mimetypes.guess_type(relative)[0] or "application/octet-stream"
        return RetrievedFile(content=content, content_type=content_type)

    def public_url(self, relative_or_public_path: str) -> str:
        relative = self._normalize_relative(relative_or_public_path)
        path = self._build_public_path(relative)
        if path.startswith("http"):
            return path
        return f"{self.api_base}/{path.lstrip('/')}"


storage_service = StorageService()
