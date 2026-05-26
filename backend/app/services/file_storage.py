"""File storage service for chat file uploads.

Supports local filesystem and S3 storage.
Files are organized per-user: {storage_root}/{user_id}/{uuid}_{filename}
"""

import logging
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "text/css",
    "text/xml",
    "text/x-python",
    "text/javascript",
    "text/x-yaml",
    "application/json",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/x-yaml",
}

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


def classify_file(mime_type: str, filename: str) -> str:
    """Classify file type based on MIME type and extension."""
    if mime_type in IMAGE_MIME_TYPES:
        return "image"
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return "pdf"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "docx" or "wordprocessingml" in mime_type:
        return "docx"
    return "text"


def make_storage_filename(filename: str) -> str:
    """Create a unique storage filename to prevent collisions."""
    return f"{uuid.uuid4().hex[:12]}_{filename}"


class BaseFileStorage(ABC):
    """Abstract file storage backend."""

    @abstractmethod
    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        """Save file and return storage path/key."""

    @abstractmethod
    async def load(self, storage_path: str) -> bytes:
        """Load file bytes by storage path."""

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete file by storage path."""

    def get_full_path(self, storage_path: str) -> Path | None:
        """Return absolute filesystem path if available (local storage only)."""
        return None

    def get_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str | None:
        """Return a presigned URL for direct client access (S3 only)."""
        return None


class LocalFileStorage(BaseFileStorage):
    """Store files on local filesystem."""

    def __init__(self, base_dir: str | Path = "media"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_name = make_storage_filename(filename)
        file_path = user_dir / storage_name
        file_path.write_bytes(data)
        return f"{user_id}/{storage_name}"

    async def load(self, storage_path: str) -> bytes:
        file_path = self.base_dir / storage_path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        return file_path.read_bytes()

    async def delete(self, storage_path: str) -> None:
        file_path = self.base_dir / storage_path
        if file_path.exists():
            file_path.unlink()

    def get_full_path(self, storage_path: str) -> Path | None:
        """Return absolute filesystem path for local files."""
        file_path = self.base_dir / storage_path
        return file_path if file_path.exists() else None


class S3FileStorage(BaseFileStorage):
    """Store files in AWS S3."""

    def __init__(self, bucket: str, region: str, prefix: str = "") -> None:
        import boto3

        self.bucket = bucket
        self.prefix = prefix
        self._client: Any = boto3.client("s3", region_name=region)

    def _key(self, storage_path: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{storage_path}"
        return storage_path

    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        storage_name = make_storage_filename(filename)
        storage_path = f"{user_id}/{storage_name}"
        self._client.put_object(
            Bucket=self.bucket,
            Key=self._key(storage_path),
            Body=data,
        )
        return storage_path

    async def load(self, storage_path: str) -> bytes:
        try:
            response = self._client.get_object(
                Bucket=self.bucket, Key=self._key(storage_path)
            )
            return response["Body"].read()
        except self._client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"File not found in S3: {storage_path}") from None

    async def delete(self, storage_path: str) -> None:
        self._client.delete_object(
            Bucket=self.bucket, Key=self._key(storage_path)
        )

    def get_presigned_url(self, storage_path: str, expires_in: int = 3600) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._key(storage_path)},
            ExpiresIn=expires_in,
        )


def get_file_storage() -> BaseFileStorage:
    """Factory: create file storage backend based on settings."""
    from app.core.config import settings

    if settings.S3_MEDIA_BUCKET:
        return S3FileStorage(
            bucket=settings.S3_MEDIA_BUCKET,
            region=settings.S3_MEDIA_REGION,
            prefix=settings.S3_MEDIA_PREFIX,
        )
    media_dir = getattr(settings, "MEDIA_DIR", "media")
    return LocalFileStorage(base_dir=media_dir)
