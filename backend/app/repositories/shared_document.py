"""Shared document repository (PostgreSQL async)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shared_document import SharedDocument


async def get_by_id(db: AsyncSession, doc_id: UUID) -> SharedDocument | None:
    return await db.get(SharedDocument, doc_id)


async def get_by_storage_name(db: AsyncSession, storage_name: str) -> SharedDocument | None:
    result = await db.execute(
        select(SharedDocument).where(SharedDocument.storage_name == storage_name)
    )
    return result.scalar_one_or_none()


async def get_all(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[SharedDocument], int]:
    total_result = await db.execute(select(func.count(SharedDocument.id)))
    total = total_result.scalar_one()

    query = (
        select(SharedDocument)
        .order_by(SharedDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def create(
    db: AsyncSession,
    *,
    filename: str,
    storage_name: str,
    filesize: int,
    content_type: str,
    uploaded_by_id: UUID,
    description: str | None = None,
) -> SharedDocument:
    doc = SharedDocument(
        filename=filename,
        storage_name=storage_name,
        filesize=filesize,
        content_type=content_type,
        uploaded_by_id=uploaded_by_id,
        description=description,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


async def delete(db: AsyncSession, doc_id: UUID) -> SharedDocument | None:
    doc = await get_by_id(db, doc_id)
    if doc:
        await db.delete(doc)
        await db.flush()
    return doc
