"""Shared document service — file storage on EFS accessible to all users."""

import logging
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.repositories import shared_document_repo
from app.schemas.shared_document import SharedDocumentList, SharedDocumentRead

logger = logging.getLogger(__name__)


class SharedDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._root = Path(settings.EFS_MOUNT_DIR)

    def _ensure_root(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        *,
        filename: str,
        data: bytes,
        content_type: str,
        uploaded_by_id: UUID,
        description: str | None = None,
    ) -> SharedDocumentRead:
        self._ensure_root()

        storage_name = f"{uuid.uuid4().hex[:12]}_{filename}"
        dest = self._root / storage_name
        dest.write_bytes(data)

        doc = await shared_document_repo.create(
            self.db,
            filename=filename,
            storage_name=storage_name,
            filesize=len(data),
            content_type=content_type,
            uploaded_by_id=uploaded_by_id,
            description=description,
        )
        return self._to_read(doc)

    async def list_documents(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> SharedDocumentList:
        docs, total = await shared_document_repo.get_all(
            self.db, skip=skip, limit=limit
        )
        return SharedDocumentList(
            items=[self._to_read(d) for d in docs],
            total=total,
        )

    async def get_download_path(self, doc_id: UUID) -> tuple[Path, str, str]:
        doc = await shared_document_repo.get_by_id(self.db, doc_id)
        if not doc:
            raise NotFoundError(message="Document not found", details={"doc_id": str(doc_id)})
        file_path = self._root / doc.storage_name
        if not file_path.exists():
            raise NotFoundError(message="File not found on disk", details={"doc_id": str(doc_id)})
        return file_path, doc.filename, doc.content_type

    async def delete_document(self, doc_id: UUID, user_id: UUID, is_admin: bool) -> None:
        doc = await shared_document_repo.get_by_id(self.db, doc_id)
        if not doc:
            raise NotFoundError(message="Document not found", details={"doc_id": str(doc_id)})
        if not is_admin and doc.uploaded_by_id != user_id:
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError(message="You can only delete your own files")

        file_path = self._root / doc.storage_name
        if file_path.exists():
            file_path.unlink()

        await shared_document_repo.delete(self.db, doc_id)

    @staticmethod
    def _to_read(doc: object) -> SharedDocumentRead:
        from app.db.models.shared_document import SharedDocument

        d: SharedDocument = doc  # type: ignore[assignment]
        uploader_name: str | None = None
        if d.uploaded_by:
            uploader_name = d.uploaded_by.full_name or d.uploaded_by.email
        return SharedDocumentRead(
            id=d.id,
            filename=d.filename,
            filesize=d.filesize,
            content_type=d.content_type,
            description=d.description,
            uploaded_by_id=d.uploaded_by_id,
            uploaded_by_name=uploader_name,
            created_at=d.created_at,
        )
