"""Background task handlers for RAG ingestion and sync operations.

Used by FastAPI BackgroundTasks when no distributed task queue is configured.
"""

import logging
import tempfile
from pathlib import Path

from app.db.session import get_db_context
from app.rag.connectors import CONNECTOR_REGISTRY
from app.rag.ingestion import IngestionService
from app.services.rag_document import RAGDocumentService
from app.services.rag_sync import RAGSyncService
from app.services.sync_source import SyncSourceService

logger = logging.getLogger(__name__)


async def ingest_document_in_background(
    doc_id: str,
    collection: str,
    filepath: str,
    source: str,
    replace: bool,
) -> None:
    """Ingest a single document into the vector store and update its DB record."""
    try:
        svc = IngestionService.from_settings()
        result = await svc.ingest_file(
            filepath=Path(filepath),
            collection_name=collection,
            replace=replace,
            source_path=source,
        )
        async with get_db_context() as db:
            doc_svc = RAGDocumentService(db)
            await doc_svc.complete_ingestion(doc_id, vector_document_id=result.document_id)
    except Exception as exc:
        logger.error("Background ingestion failed: %s", exc)
        async with get_db_context() as db:
            doc_svc = RAGDocumentService(db)
            await doc_svc.fail_ingestion(doc_id, error_message=str(exc))
    finally:
        Path(filepath).unlink(missing_ok=True)


async def sync_local_in_background(
    log_id: str,
    collection: str,
    mode: str,
    path: str,
) -> None:
    """Sync a local directory into a collection and update the sync log."""
    svc = IngestionService.from_settings()
    ingested = skipped = failed = total = 0

    try:
        target = Path(path)
        files = list(target.rglob("*")) if target.is_dir() else [target]
        files = [f for f in files if f.is_file()]
        total = len(files)
        for filepath in files:
            try:
                await svc.ingest_file(
                    filepath=filepath,
                    collection_name=collection,
                    replace=(mode == "full"),
                    source_path=str(filepath),
                )
                ingested += 1
            except Exception as e:
                logger.warning("Failed to ingest %s: %s", filepath, e)
                failed += 1
    except Exception as e:
        logger.error("Sync failed: %s", e)

    async with get_db_context() as db:
        sync_svc = RAGSyncService(db)
        try:
            await sync_svc.complete_sync(
                log_id,
                status="done" if not failed else "error",
                total_files=total,
                ingested=ingested,
                skipped=skipped,
                failed=failed,
            )
        except Exception:
            logger.error("Sync log %s not found during background update", log_id)


async def sync_source_in_background(source_id: str, log_id: str) -> None:
    """Execute a configured sync source and update the sync log."""
    async with get_db_context() as db:
        source_svc = SyncSourceService(db)
        sync_svc = RAGSyncService(db)
        try:
            source = await source_svc.get_source(source_id)
            connector_cls = CONNECTOR_REGISTRY.get(source.connector_type)
            if not connector_cls:
                await sync_svc.complete_sync(
                    log_id,
                    status="error",
                    error_message=f"Unknown connector: {source.connector_type}",
                )
                return
            connector = connector_cls()
            config = source.config if isinstance(source.config, dict) else {}
            files = await connector.list_files(config)
            ingestion = IngestionService.from_settings()
            ingested = failed = 0
            with tempfile.TemporaryDirectory() as tmp_dir:
                for f in files:
                    try:
                        local_path = await connector.download_file(f, Path(tmp_dir))
                        await ingestion.ingest_file(
                            filepath=local_path,
                            collection_name=source.collection_name,
                            replace=(source.sync_mode == "full"),
                            source_path=f.source_path,
                        )
                        ingested += 1
                    except Exception as e:
                        logger.warning("Sync file failed %s: %s", f.name, e)
                        failed += 1
            await sync_svc.complete_sync(
                log_id,
                status="done" if not failed else "error",
                total_files=len(files),
                ingested=ingested,
                failed=failed,
            )
        except Exception as e:
            logger.error("Source sync failed: %s", e)
            await sync_svc.complete_sync(log_id, status="error", error_message=str(e))
