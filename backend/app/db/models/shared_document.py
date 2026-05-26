"""SharedDocument model — tracks files uploaded to shared EFS storage."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class SharedDocument(TimestampMixin, Base):
    """A file stored on shared EFS, visible to all authenticated users."""

    __tablename__ = "shared_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    filesize: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SharedDocument(id={self.id}, filename={self.filename})>"
