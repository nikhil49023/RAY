"""
web_rag.py — Crawl4AI-Powered Web Retrieval
--------------------------------------------
Uses Crawl4AI for fast, local-first web scraping and content extraction.
"""

import asyncio
import logging
import re
from typing import List, Dict, Any
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from core.state import AgentState

logger = logging.getLogger("ray.web_rag")

# Default crawler configuration
BROWSER_CONFIG = BrowserConfig(
    headless=True,
    verbose=False,
)

DEFAULT_CRAWLER_CONFIG = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    word_count_threshold=10,
    exclude_external_links=True,
    exclude_social_media_links=True,
    process_iframes=True,
    remove_overlay_elements=True,
    simulate_user=True,
    override_navigator=True,
)


def _extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    pattern = re.compile(r"https?://[^\s]+", flags=re.IGNORECASE)
    return pattern.findall(text)


async def _crawl_urls_async(urls: List[str]) -> List[Dict[str, Any]]:
    """Asynchronously crawl multiple URLs using Crawl4AI."""
    results = []

    async with AsyncWebCrawler(config=BROWSER_CONFIG) as crawler:
        for url in urls:
            try:
                logger.info(f"Crawling URL: {url}")
                result = await crawler.arun(url=url, config=DEFAULT_CRAWLER_CONFIG)
                markdown = (
                    getattr(result, "markdown_raw", None)
                    or getattr(result, "markdown", None)
                    or ""
                )

                if result.success and markdown:
                    results.append(
                        {
                            "content": markdown,
                            "url": url,
                            "source": "crawl4ai",
                            "title": getattr(result, "title", "")
                            or urlparse(url).netloc,
                        }
                    )
                else:
                    logger.warning(
                        f"Failed to crawl {url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}"
                    )

            except Exception as e:
                logger.error(f"Error crawling {url}: {str(e)}")
                continue

    return results


def web_rag(state: AgentState) -> AgentState:
    """Discover candidate URLs with DuckDuckGo and scrape via Crawl4AI."""

    query = str(state.get("user_query", "")).strip()
    if not query:
        state["web_rag_results"] = []
        return state

    # Extract URLs from query
    urls = _extract_urls(query)

    # If no URLs in query, search with DuckDuckGo
    if not urls:
        try:
            from agents.api_handlers import MultiProviderClients

            client = MultiProviderClients()
            search_results = client.search_web(query, max_results=3)
            urls = [item.get("url", "") for item in search_results if item.get("url")]
            urls = [url for url in urls if url]  # Filter empty strings
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            urls = []

    if not urls:
        state["web_rag_results"] = []
        return state

    # Limit to top 3 URLs to avoid overload
    urls = urls[:3]

    # Run async crawl
    try:
        results = asyncio.run(_crawl_urls_async(urls))
        state["web_rag_results"] = results

        if not results:
            state["error"] = (
                "Web RAG failed: Crawl4AI returned no results for provided URLs"
            )

    except Exception as e:
        logger.error(f"Web RAG crawling failed: {e}")
        state["web_rag_results"] = []
        state["error"] = f"Web RAG failed: {str(e)}"

    return state
