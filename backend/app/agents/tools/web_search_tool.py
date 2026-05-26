"""Web search tool using DuckDuckGo (ddgs)."""

import asyncio
import logging

from ddgs import DDGS

logger = logging.getLogger(__name__)


def _search(query: str, max_results: int, region: str) -> list[dict[str, str]]:
    return DDGS().text(query, max_results=max_results, region=region)


async def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
) -> str:
    """Search the internet via DuckDuckGo and return formatted results."""
    max_results = max(1, min(max_results, 10))

    logger.debug("web search: query=%s, max_results=%s, region=%s", query, max_results, region)

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search, query, max_results, region),
            timeout=15,
        )
    except TimeoutError:
        logger.warning("Web search timed out for query: %s", query)
        return "Web search timed out. Please try again with a simpler query."
    except Exception:
        logger.exception("Web search failed")
        return "Web search failed. Please try again with a different query."

    if not results:
        return "No results found for the given query."

    formatted = []
    for i, r in enumerate(results, start=1):
        title = r.get("title", "No title")
        url = r.get("href", "")
        snippet = r.get("body", "No description")
        formatted.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}")

    return "Web search results:\n\n" + "\n\n".join(formatted)
