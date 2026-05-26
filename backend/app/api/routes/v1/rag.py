"""RAG API routes for collection management, search, document upload, and deletion."""

import asyncio
import io
import logging
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import (
    CurrentAdmin,
    CurrentUser,
    IngestionSvc,
    KBClientSvc,
    RAGDocumentSvc,
)
from app.core.config import settings as app_settings
from app.core.exceptions import NotFoundError
from app.rag.config import get_supported_formats
from app.rag.models import IngestionStatus
from app.schemas.rag import (
    RAGCollectionInfo,
    RAGCollectionList,
    RAGDocumentList,
    RAGIngestResponse,
    RAGMessageResponse,
    RAGRetryResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    RAGSearchResult,
    RAGTrackedDocumentList,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/supported-formats")
async def get_supported_formats_endpoint() -> Any:
    """Return file formats supported by the current PDF parser configuration."""
    parser_name = getattr(app_settings, "PDF_PARSER", "pymupdf")
    return {"parser": parser_name, "formats": sorted(get_supported_formats(parser_name))}


@router.get("/collections", response_model=RAGCollectionList)
async def list_collections(
    kb_client: KBClientSvc,
    _: CurrentAdmin,
) -> Any:
    """List all available collections."""
    names = await kb_client.list_collections()
    return RAGCollectionList(items=names)


@router.post(
    "/collections/{name}", status_code=status.HTTP_201_CREATED, response_model=RAGMessageResponse
)
async def create_collection(
    name: str,
    _: CurrentAdmin,
) -> Any:
    """Create a new collection (S3 prefix — created on first upload)."""
    return RAGMessageResponse(message=f"Collection '{name}' created successfully.")


@router.delete("/collections/{name}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def drop_collection(
    name: str,
    kb_client: KBClientSvc,
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
) -> None:
    """Drop an entire collection — S3 objects and all SQL document records."""
    await kb_client.delete_collection(name)
    await rag_doc_svc.delete_by_collection(name)


@router.get("/collections/{name}/info", response_model=RAGCollectionInfo)
async def get_collection_info(
    name: str,
    kb_client: KBClientSvc,
    _: CurrentAdmin,
) -> Any:
    """Retrieve stats for a specific collection."""
    return await kb_client.get_collection_info(name)


@router.get("/collections/{name}/documents", response_model=RAGDocumentList)
async def list_documents(
    name: str,
    kb_client: KBClientSvc,
    _: CurrentAdmin,
) -> Any:
    """List all documents in a specific collection."""
    from app.schemas.rag import RAGDocumentItem

    docs = await kb_client.list_documents(name)
    return RAGDocumentList(
        items=[
            RAGDocumentItem(
                document_id=doc.document_id,
                filename=doc.filename,
                filesize=doc.filesize,
                filetype=doc.filetype,
                chunk_count=doc.chunk_count,
                additional_info=doc.additional_info,
            )
            for doc in docs
        ],
        total=len(docs),
    )


@router.post("/search", response_model=RAGSearchResponse)
async def search_documents(
    request: RAGSearchRequest,
    kb_client: KBClientSvc,
    current_user: CurrentUser,
) -> Any:
    """Search for relevant document chunks via Bedrock Knowledge Base."""
    collection = (
        request.collection_names[0] if request.collection_names else request.collection_name
    )
    results = await kb_client.retrieve(
        query=request.query,
        top_k=request.limit,
        collection_name=collection if collection != "all" else None,
    )
    if request.min_score:
        results = [r for r in results if r.score >= request.min_score]
    api_results = [RAGSearchResult(**hit.model_dump()) for hit in results]
    return RAGSearchResponse(results=api_results)


@router.delete(
    "/collections/{name}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_document(
    name: str,
    document_id: str,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
) -> None:
    """Delete a specific document by its ID from a collection."""
    success = await ingestion_service.remove_document(name, document_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post(
    "/collections/{name}/ingest", response_model=RAGIngestResponse, response_model_exclude_none=True
)
async def ingest_file(
    name: str,
    rag_doc_svc: RAGDocumentSvc,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
    file: UploadFile = File(...),
    replace: bool = Query(False),
) -> Any:
    """Upload a file directly to S3 and trigger Bedrock KB ingestion."""
    ALLOWED = get_supported_formats(getattr(app_settings, "PDF_PARSER", "pymupdf"))
    max_size = app_settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(sorted(ALLOWED))}",
        )

    data = await file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=413, detail=f"File too large. Maximum {app_settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    rag_doc = await rag_doc_svc.create_document(
        collection_name=name,
        filename=filename,
        filesize=len(data),
        filetype=ext.lstrip("."),
    )
    doc_id = str(rag_doc.id)

    try:
        result = await ingestion_service.ingest_bytes(
            file_data=data,
            filename=filename,
            collection_name=name,
        )
        if result.status == IngestionStatus.ERROR:
            await rag_doc_svc.fail_ingestion(
                doc_id, error_message=result.error_message or "Unknown"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed: {result.error_message}",
            )
        await rag_doc_svc.complete_ingestion(doc_id, vector_document_id=result.document_id)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "id": doc_id,
                "status": "done",
                "filename": filename,
                "collection": name,
                "message": result.message or "File uploaded and ingestion started.",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        await rag_doc_svc.fail_ingestion(doc_id, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e


@router.get("/documents", response_model=RAGTrackedDocumentList)
async def list_rag_documents(
    rag_doc_svc: RAGDocumentSvc,
    _: CurrentAdmin,
    collection_name: str | None = Query(None),
) -> Any:
    """List tracked RAG documents."""
    return await rag_doc_svc.list_documents(collection_name)


@router.get("/documents/{doc_id}/download")
async def download_rag_document(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    kb_client: KBClientSvc,
    _: CurrentAdmin,
) -> Any:
    """Download the original file from S3."""
    try:
        s3_key, filename, mime_type = await rag_doc_svc.get_download_info(doc_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e

    try:
        file_bytes = await kb_client.download_document(s3_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found in S3: {e}") from e

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_rag_document(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
) -> None:
    """Delete a document from SQL, vector store, and file storage."""

    try:
        await rag_doc_svc.delete_document(doc_id, ingestion_service)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/documents/{doc_id}/retry", response_model=RAGRetryResponse)
async def retry_ingestion(
    doc_id: str,
    rag_doc_svc: RAGDocumentSvc,
    kb_client: KBClientSvc,
    ingestion_service: IngestionSvc,
    _: CurrentAdmin,
) -> Any:
    """Retry a failed document ingestion by re-triggering Bedrock KB sync."""

    try:
        doc = await rag_doc_svc.retry_ingestion(doc_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    s3_key = doc.vector_document_id
    if not s3_key:
        await rag_doc_svc.fail_ingestion(
            doc_id, error_message="No S3 key found — please re-upload the file"
        )
        raise HTTPException(
            status_code=400,
            detail="Cannot retry: file was never uploaded to S3. Please re-upload.",
        )

    try:
        job_id = await kb_client.start_ingestion_job()
        await rag_doc_svc.complete_ingestion(doc_id, vector_document_id=s3_key)
        return RAGRetryResponse(
            id=str(doc.id),
            status="done",
            message=f"Re-ingestion triggered — job {job_id} started",
        )
    except Exception as e:
        await rag_doc_svc.fail_ingestion(doc_id, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Retry failed: {e}") from e


# SSE for RAG status updates (auto-reconnect via EventSource API)
@router.get("/status/stream", response_class=EventSourceResponse)
async def rag_status_stream() -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for real-time RAG ingestion status updates.

    Subscribes to Redis pub/sub channel 'rag_status' and streams events.
    Browser auto-reconnects via EventSource API.
    """
    if not app_settings.REDIS_ENABLED:
        yield ServerSentEvent(raw_data='{"error":"Redis disabled"}', event="error", id="0")
        return

    r = aioredis.from_url(app_settings.REDIS_URL)  # type: ignore[no-untyped-call]
    pubsub = r.pubsub()
    await pubsub.subscribe("rag_status")
    event_id = 0

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = (
                    message["data"].decode()
                    if isinstance(message["data"], bytes)
                    else message["data"]
                )
                event_id += 1
                yield ServerSentEvent(raw_data=data, event="status", id=str(event_id))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"RAG SSE error: {e}")
    finally:
        try:
            await pubsub.unsubscribe("rag_status")
            await r.aclose()
        except Exception:
            pass
