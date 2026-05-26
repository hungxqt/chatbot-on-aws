from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.rag.bedrock_kb import BedrockKBClient
from app.rag.models import IngestionResult, IngestionStatus

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates document upload to S3 and triggers Bedrock KB ingestion."""

    def __init__(
        self,
        kb_client: BedrockKBClient,
        on_event: Callable[..., Awaitable[None]] | None = None,
    ):
        self.kb_client = kb_client
        self._on_event = on_event

    @classmethod
    def from_settings(
        cls,
        on_event: Callable[..., Awaitable[None]] | None = None,
    ) -> IngestionService:
        """Build an IngestionService using the application's settings."""
        kb_client = BedrockKBClient.from_settings()
        return cls(kb_client=kb_client, on_event=on_event)

    async def _emit(self, event: str, data: dict[str, object]) -> None:
        if self._on_event:
            try:
                await self._on_event(event, data)
            except Exception as e:
                logger.warning(f"Webhook event dispatch failed: {e}")

    async def ingest_bytes(
        self,
        file_data: bytes,
        filename: str,
        collection_name: str,
    ) -> IngestionResult:
        """Upload raw bytes to S3 and trigger Bedrock KB ingestion."""
        try:
            s3_key = await self.kb_client.upload_document(
                file_data=file_data,
                filename=filename,
                collection_name=collection_name,
            )

            job_id = await self.kb_client.start_ingestion_job()

            await self._emit(
                "rag.document.ingested",
                {
                    "document_id": s3_key,
                    "filename": filename,
                    "collection": collection_name,
                    "action": "ingested",
                    "ingestion_job_id": job_id,
                },
            )

            return IngestionResult(
                status=IngestionStatus.DONE,
                document_id=s3_key,
                message=f"Successfully uploaded '{filename}' — ingestion job {job_id} started",
            )

        except Exception as e:
            logger.error(f"Ingestion error for {filename}: {e!s}", exc_info=True)
            return IngestionResult(
                status=IngestionStatus.ERROR,
                error_message=str(e),
                message=f"Failed to process {filename}",
            )

    async def ingest_file(
        self,
        filepath: Path,
        collection_name: str,
        replace: bool = True,
        source_path: str = "",
    ) -> IngestionResult:
        """Upload a file to S3 and trigger Bedrock KB ingestion."""
        try:
            file_data = filepath.read_bytes()
            filename = Path(source_path).name if source_path else filepath.name

            s3_key = await self.kb_client.upload_document(
                file_data=file_data,
                filename=filename,
                collection_name=collection_name,
            )

            job_id = await self.kb_client.start_ingestion_job()

            await self._emit(
                "rag.document.ingested",
                {
                    "document_id": s3_key,
                    "filename": filename,
                    "collection": collection_name,
                    "action": "ingested",
                    "ingestion_job_id": job_id,
                    "source_path": source_path or str(filepath),
                },
            )

            return IngestionResult(
                status=IngestionStatus.DONE,
                document_id=s3_key,
                message=f"Successfully uploaded '{filename}' — ingestion job {job_id} started",
            )

        except Exception as e:
            logger.error(f"Ingestion error for {filepath.name}: {e!s}")
            return IngestionResult(
                status=IngestionStatus.ERROR,
                error_message=str(e),
                message=f"Failed to process {filepath.name}",
            )

    async def remove_document(self, collection_name: str, document_id: str) -> bool:
        """Delete a document from S3."""
        try:
            await self.kb_client.delete_document(document_id)
            await self._emit(
                "rag.document.deleted",
                {
                    "document_id": document_id,
                    "collection": collection_name,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e!s}")
            return False
