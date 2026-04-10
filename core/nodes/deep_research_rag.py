"""
deep_research_rag.py — Crawl4AI Deep Research
------------------------------------------------
Deep domain crawling using local Crawl4AI.
Only runs when research_level == 'deep'.
"""

import asyncio
import logging
from typing import Any, Dict, List
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from core.llm_factory import LLMFactory
from core.state import AgentState
from core.relevance import rerank_with_relu

# Configure logging
logger = logging.getLogger("ray.deep_research")

MAX_SCRAPED_URLS = 4
MAX_SCRAPE_CHARS = 3000
MAX_SUMMARY_INPUT_CHARS = 12000
DEEP_RESEARCH_SUMMARY_MODEL = "groq/openai/gpt-oss-20b"

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
                            "title": getattr(result, "title", "")
                            or urlparse(url).netloc,
                            "markdown": markdown,
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


def _summarize_scraped_pages(
    state: AgentState, scraped_data: List[Dict[str, str]]
) -> str:
    if not scraped_data:
        return ""

    combined_content = "\n\n".join(
        f"Content from {item['url']}:\n{str(item.get('content', ''))[:MAX_SCRAPE_CHARS]}"
        for item in scraped_data
    )[:MAX_SUMMARY_INPUT_CHARS]

    temperature = float(state.get("temperature", 0.1))
    llm = LLMFactory.get_model(
        model_id=DEEP_RESEARCH_SUMMARY_MODEL, temperature=temperature
    )
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are summarizing scraped research notes for an agent pipeline. "
                    "Return concise markdown with these sections exactly: "
                    "## Executive Summary, ## Key Findings, ## Important URLs. "
                    "Each key finding should be one bullet grounded in the scraped content."
                )
            ),
            HumanMessage(
                content=f"Summarize these scraped websites:\n\n{combined_content}"
            ),
        ]
    )
    return str(response.content).strip()


def deep_research_rag(state: AgentState) -> dict:
    """
    Perform deep research using Crawl4AI.

    Args:
        state: Current agent state with query and research_level

    Returns:
        Dictionary with evidence and thinking_log
    """
    query = state.get("rewritten_query") or state["messages"][-1].content
    research_level = state.get("research_level", "basic")

    if research_level != "deep":
        logger.debug("Skipping deep research - research level is not 'deep'")
        return {"evidence": [], "current_task": "Deep research skipped"}

    logger.info(f"Starting deep research for query: {query[:100]}...")

    evidence: List[Dict[str, Any]] = []
    scraped_data: List[Dict[str, str]] = []
    deep_research_summary = ""

    # Get search results
    try:
        from agents.api_handlers import MultiProviderClients

        client = MultiProviderClients()
        search_results = client.search_web(query, max_results=8)
        raw_items = []
        for item in search_results:
            url = item.get("url")
            if url:
                raw_items.append(
                    {
                        "url": url,
                        "title": item.get("title", ""),
                        "description": item.get("snippet", ""),
                    }
                )
    except ImportError as e:
        logger.error(f"Failed to import MultiProviderClients: {e}")
        return {
            "evidence": [],
            "current_task": "Deep research: Backend import failed",
            "thinking_log": [
                {
                    "node": "deep_research",
                    "title": "Crawl4AI deep research failed",
                    "detail": "Backend import failed",
                    "provider": "crawl4ai",
                }
            ],
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            "evidence": [],
            "current_task": "Deep research: Search failed",
            "thinking_log": [
                {
                    "node": "deep_research",
                    "title": "Crawl4AI deep research failed",
                    "detail": f"Search failed: {e}",
                    "provider": "crawl4ai",
                }
            ],
        }

    candidate_urls = [item["url"] for item in raw_items][:MAX_SCRAPED_URLS]

    if not candidate_urls:
        return {
            "evidence": [],
            "current_task": "Deep research: No candidate URLs",
            "thinking_log": [
                {
                    "node": "deep_research",
                    "title": "Crawl4AI deep research failed",
                    "detail": "No URLs found",
                    "provider": "crawl4ai",
                }
            ],
        }

    logger.info(f"Scraping {len(candidate_urls)} URLs with Crawl4AI")

    try:
        scraped_data = asyncio.run(_crawl_urls_async(candidate_urls))
    except Exception as e:
        logger.error(f"Crawl4AI scraping failed: {e}")

    if scraped_data:
        try:
            deep_research_summary = _summarize_scraped_pages(state, scraped_data)
        except Exception as summary_error:
            logger.error(f"Failed to summarize scraped content: {summary_error}")

    # Rerank with ReLU
    ranked_items = rerank_with_relu(
        query,
        raw_items,
        lambda row: " ".join(
            [
                str(row.get("title", "")),
                str(row.get("description", ""))[:1000],
                str(row.get("url", "")),
            ]
        ),
    )

    for item in ranked_items[:8]:
        relu_score = float(item.get("relu_score", 0.0))
        matching_scrape = next(
            (row for row in scraped_data if row["url"] == item.get("url")),
            None,
        )
        evidence.append(
            {
                "source": "Crawl4AI deep research",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "claim": (
                    (matching_scrape or {}).get("content")
                    or item.get("description", "")
                    or item.get("title", "")
                )[:500],
                "type": "web",
                "confidence": min(0.99, 0.62 + (relu_score / 5.5)),
                "provider": "crawl4ai",
                "relu_score": relu_score,
            }
        )

    return {
        "evidence": evidence,
        "scraped_data": scraped_data,
        "deep_research_summary": deep_research_summary,
        "current_task": f"Deep research: {len(evidence)} pages crawled",
        "thinking_log": [
            {
                "node": "deep_research",
                "title": "Crawl4AI deep research completed"
                if evidence
                else "Crawl4AI deep research failed",
                "detail": f"Scraped {len(scraped_data)} pages, and reranked {len(evidence)} pages with ReLU."
                if evidence
                else "No results returned.",
                "provider": "crawl4ai",
                "result_count": len(evidence),
            }
        ],
    }
