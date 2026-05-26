"""Shared document schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SharedDocumentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class SharedDocumentCreate(SharedDocumentBase):
    description: str | None = Field(default=None, max_length=500)


class SharedDocumentRead(SharedDocumentBase):
    id: UUID
    filename: str
    filesize: int
    content_type: str
    description: str | None = None
    uploaded_by_id: UUID | None = None
    uploaded_by_name: str | None = None
    created_at: datetime


class SharedDocumentList(SharedDocumentBase):
    items: list[SharedDocumentRead]
    total: int
