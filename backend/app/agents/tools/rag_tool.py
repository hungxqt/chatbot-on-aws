"""RAG tool for agent knowledge base search."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.rag.bedrock_kb import BedrockKBClient

_kb_client: "BedrockKBClient | None" = None


def _get_kb_client() -> "BedrockKBClient":
    """Get or create Bedrock KB client singleton."""
    global _kb_client
    if _kb_client is not None:
        return _kb_client
    from app.rag.bedrock_kb import BedrockKBClient

    _kb_client = BedrockKBClient.from_settings()
    return _kb_client


async def search_knowledge_base(
    query: str,
    collection: str | None = None,
    collections: list[str] | None = None,
    top_k: int = 5,
) -> str:
    """Search the knowledge base and return formatted results."""
    client = _get_kb_client()

    if collections and len(collections) > 1:
        all_results = []
        for col in collections:
            results = await client.retrieve(query=query, top_k=top_k, collection_name=col)
            all_results.extend(results)
        all_results.sort(key=lambda r: r.score, reverse=True)
        results = all_results[:top_k]
    elif collection:
        results = await client.retrieve(query=query, top_k=top_k, collection_name=collection)
    else:
        results = await client.retrieve(query=query, top_k=top_k)

    if not results:
        return "No relevant documents found in the knowledge base."

    formatted_results = []
    for i, result in enumerate(results, start=1):
        source = result.metadata.get("filename", "unknown")
        page = result.metadata.get("page_num", "")
        chunk = result.metadata.get("chunk_num", "")
        col = result.metadata.get("collection", "")
        page_info = f", page {page}" if page else ""
        chunk_info = f", chunk {chunk}" if chunk else ""
        col_info = f" [{col}]" if col else ""

        formatted_results.append(
            f"[{i}] Source: {source}{page_info}{chunk_info}{col_info} (score: {result.score:.3f})\n"
            f"{result.content}"
        )

    return "Search results (cite sources using [1], [2], etc. in your response):\n\n" + "\n\n".join(
        formatted_results
    )


def _run_async_search(query: str, collection: str, top_k: int) -> str:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(search_knowledge_base(query, collection, top_k=top_k))
    finally:
        loop.close()


def search_knowledge_base_sync(
    query: str,
    collection: str = "documents",
    top_k: int = 5,
) -> str:
    """Synchronous wrapper for search_knowledge_base."""
    logger.debug(
        "search_knowledge_base_sync called: query=%s, collection=%s, top_k=%s",
        query,
        collection,
        top_k,
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_async_search, query, collection, top_k)
            result = future.result()
        logger.debug("search_knowledge_base_sync completed successfully")
        return result
    except Exception as e:
        logger.error(
            "search_knowledge_base_sync failed: %s",
            str(e),
            exc_info=True,
        )
        raise


__all__ = ["search_knowledge_base", "search_knowledge_base_sync"]
