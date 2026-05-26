"""Shared document endpoints — EFS-backed cloud storage for all users."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, SharedDocumentSvc
from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.user import UserRole
from app.schemas.shared_document import SharedDocumentList, SharedDocumentRead

router = APIRouter()


@router.post("", response_model=SharedDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_shared_document(
    service: SharedDocumentSvc,
    user: CurrentUser,
    file: UploadFile = File(...),
    description: str | None = Query(None, max_length=500),
) -> Any:
    """Upload a file to shared EFS storage."""
    max_size = settings.EFS_MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = await file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {settings.EFS_MAX_UPLOAD_SIZE_MB}MB.",
        )
    filename = file.filename or "unknown"
    content_type = file.content_type or "application/octet-stream"
    return await service.upload(
        filename=filename,
        data=data,
        content_type=content_type,
        uploaded_by_id=user.id,
        description=description,
    )


@router.get("", response_model=SharedDocumentList)
async def list_shared_documents(
    service: SharedDocumentSvc,
    _: CurrentUser,
    skip: int = Query(0, ge=0, description="Items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
) -> Any:
    """List all shared documents."""
    return await service.list_documents(skip=skip, limit=limit)


@router.get("/{doc_id}/download")
async def download_shared_document(
    doc_id: UUID,
    service: SharedDocumentSvc,
    _: CurrentUser,
) -> Any:
    """Download a shared document."""
    try:
        file_path, filename, content_type = await service.get_download_path(doc_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return FileResponse(path=file_path, filename=filename, media_type=content_type)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_shared_document(
    doc_id: UUID,
    service: SharedDocumentSvc,
    user: CurrentUser,
) -> None:
    """Delete a shared document. Owners and admins only."""
    try:
        is_admin = user.has_role(UserRole.ADMIN)
        await service.delete_document(doc_id, user.id, is_admin)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=e.message) from e
