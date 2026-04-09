"""
deep_research_rag.py — Firecrawl Deep Research
------------------------------------------------
Deep domain crawling using self-hosted Firecrawl.
Only runs when research_level == 'deep'.
Includes retry logic and comprehensive error handling.
"""

import logging
import time
from typing import Any, Dict, List, Tuple

import requests
from langchain_core.messages import HumanMessage, SystemMessage
from requests.exceptions import RequestException, Timeout, ConnectionError

from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.state import AgentState
from services.orchestrator.relevance import rerank_with_relu
from services.orchestrator.runtime import get_firecrawl_config, load_user_settings

# Configure logging
logger = logging.getLogger("ray.deep_research")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff delays in seconds
REQUEST_TIMEOUT = 30  # seconds
MAX_SCRAPED_URLS = 4
MAX_SCRAPE_CHARS = 3000
MAX_SUMMARY_INPUT_CHARS = 12000
FIRECRAWL_SUMMARY_MODEL = "groq/openai/gpt-oss-20b"


def _extract_firecrawl_items(result) -> list:
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, list):
            return data

    data = getattr(result, "data", None)
    if isinstance(data, list):
        return data

    # Firecrawl v2 SDK returns SearchData(web=[...])
    web_items = getattr(result, "web", None)
    if isinstance(web_items, list):
        normalized: List[Dict[str, Any]] = []
        for item in web_items:
            if isinstance(item, dict):
                normalized.append(item)
                continue

            normalized.append(
                {
                    "url": str(getattr(item, "url", "") or "").strip(),
                    "title": str(getattr(item, "title", "") or "").strip(),
                    "markdown": str(getattr(item, "description", "") or "").strip(),
                }
            )
        return normalized

    return []


def _extract_scrape_markdown(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, dict):
        return str(
            result.get("markdown") or result.get("content") or result.get("html") or ""
        )
    for attr in ("markdown", "content", "html"):
        value = getattr(result, attr, None)
        if value:
            return str(value)
    return ""


def _candidate_urls(state: AgentState, raw_items: List[Dict[str, Any]]) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()

    for item in state.get("evidence", []):
        url = str(item.get("url", "")).strip()
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
        if len(urls) >= MAX_SCRAPED_URLS:
            return urls

    for item in raw_items:
        url = str(item.get("url", "")).strip()
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
        if len(urls) >= MAX_SCRAPED_URLS:
            break

    return urls


def _summarize_scraped_pages(
    state: AgentState, scraped_data: List[Dict[str, str]]
) -> str:
    if not scraped_data:
        return ""

    combined_content = "\n\n".join(
        f"Content from {item['url']}:\n{item['content'][:MAX_SCRAPE_CHARS]}"
        for item in scraped_data
    )[:MAX_SUMMARY_INPUT_CHARS]

    temperature = float(state.get("temperature", 0.1))
    llm = LLMFactory.get_model(
        model_id=FIRECRAWL_SUMMARY_MODEL, temperature=temperature
    )
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are summarizing Firecrawl-scraped research notes for an agent pipeline. "
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


def _is_firecrawl_healthy(api_url: str) -> Tuple[bool, str]:
    """Check if Firecrawl endpoint is reachable with timeout."""
    base = api_url.rstrip("/")
    # Some self-hosted builds expose / but not /health.
    probe_paths = ["/health", "/"]
    try:
        statuses: List[str] = []
        for path in probe_paths:
            response = requests.get(f"{base}{path}", timeout=REQUEST_TIMEOUT)
            if response.ok:
                return True, ""
            statuses.append(f"{path}:{response.status_code}")
        return False, "health checks failed (" + ", ".join(statuses) + ")"
    except Timeout:
        logger.warning(f"Firecrawl health check timed out: {api_url}")
        return False, "health check timed out"
    except ConnectionError:
        logger.warning(f"Firecrawl connection refused: {api_url}")
        return False, "connection refused"
    except RequestException as exc:
        logger.warning(f"Firecrawl health check failed: {exc}")
        return False, str(exc)


def _retry_with_backoff(
    func: Any,
    args: tuple = (),
    kwargs: dict = None,
    max_retries: int = MAX_RETRIES,
    delays: List[float] = None,
) -> Tuple[bool, Any, str]:
    """
    Execute a function with retry logic and exponential backoff.

    Returns:
        Tuple of (success, result, error_message)
    """
    if kwargs is None:
        kwargs = {}
    if delays is None:
        delays = RETRY_DELAYS

    last_error = ""
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            return True, result, ""
        except Timeout:
            last_error = "request timed out"
            logger.warning(f"Request timed out (attempt {attempt + 1}/{max_retries})")
        except ConnectionError:
            last_error = "connection refused"
            logger.warning(f"Connection refused (attempt {attempt + 1}/{max_retries})")
        except RequestException as e:
            last_error = str(e)
            logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            delay = delays[min(attempt, len(delays) - 1)]
            logger.info(f"Retrying in {delay}s...")
            time.sleep(delay)

    return False, None, last_error


def deep_research_rag(state: AgentState) -> dict:
    """
    Perform deep research using Firecrawl.

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
    firecrawl_summary = ""
    settings = load_user_settings()
    config = get_firecrawl_config(settings)
    base_url = config.get("base_url", "")
    cloud_url = config.get("cloud_url", "")
    fallback_key = config.get("fallback_api_key", "")
    strategy = config.get("strategy", "self_hosted_first")

    if not base_url and not fallback_key:
        logger.warning("Firecrawl not configured - no base_url or fallback_key")
        return {
            "evidence": [],
            "current_task": "Deep research: not configured",
            "thinking_log": [
                {
                    "node": "deep_research",
                    "title": "Firecrawl unavailable",
                    "detail": "No self-hosted Firecrawl URL or cloud fallback key is configured.",
                    "provider": "firecrawl",
                }
            ],
        }

    # Build attempts list based on strategy
    attempts: List[Dict[str, str]] = []
    if base_url and strategy != "cloud_only":
        attempts.append(
            {
                "label": "self-hosted",
                "api_url": base_url,
                "api_key": "",
            }
        )
    if fallback_key:
        attempts.append(
            {
                "label": "cloud-fallback",
                "api_url": cloud_url,
                "api_key": fallback_key,
            }
        )

    attempt_errors: List[str] = []
    active_mode = ""

    try:
        from firecrawl import FirecrawlApp
    except ImportError as e:
        logger.error("Firecrawl package not installed")
        return {
            "evidence": [],
            "current_task": "Deep research: Firecrawl not installed",
            "thinking_log": [
                {
                    "node": "deep_research",
                    "title": "Firecrawl unavailable",
                    "detail": "Firecrawl package is not installed. Run: pip install firecrawl-py",
                    "provider": "firecrawl",
                }
            ],
        }

    for attempt in attempts:
        try:
            logger.info(f"Trying {attempt['label']} Firecrawl endpoint...")

            # Health check for self-hosted
            if attempt["label"] == "self-hosted":
                healthy, health_error = _is_firecrawl_healthy(attempt["api_url"])
                if not healthy:
                    attempt_errors.append(
                        f"{attempt['label']}: unavailable ({health_error})"
                    )
                    logger.warning(
                        f"Health check failed for {attempt['label']}: {health_error}"
                    )
                    continue

            # Initialize Firecrawl client
            kwargs: Dict[str, str] = {}
            if attempt["api_url"]:
                kwargs["api_url"] = attempt["api_url"]
            if attempt["api_key"]:
                kwargs["api_key"] = attempt["api_key"]

            app = FirecrawlApp(**kwargs)
            if not hasattr(app, "search"):
                attempt_errors.append(
                    f"{attempt['label']}: installed Firecrawl client has no search() method"
                )
                logger.error(
                    f"Firecrawl client missing search method for {attempt['label']}"
                )
                continue

            # Perform search with retry logic
            success, result, error = _retry_with_backoff(
                app.search, kwargs={"query": query, "limit": 8}
            )

            if not success:
                attempt_errors.append(f"{attempt['label']}: {error}")
                logger.warning(f"Search failed for {attempt['label']}: {error}")
                continue

            raw_items = _extract_firecrawl_items(result)
            if not raw_items:
                attempt_errors.append(f"{attempt['label']}: no crawl results returned")
                logger.info(f"No results from {attempt['label']}")
                continue

            logger.info(
                f"Retrieved {len(raw_items)} raw results from {attempt['label']}"
            )

            candidate_urls = _candidate_urls(state, raw_items)
            logger.info(f"Scraping {len(candidate_urls)} URLs with Firecrawl")
            for url in candidate_urls:
                scrape_success, scrape_result, scrape_error = _retry_with_backoff(
                    app.scrape_url,
                    args=(url,),
                    kwargs={
                        "formats": ["markdown"],
                        "only_main_content": True,
                    },
                )
                if not scrape_success:
                    attempt_errors.append(
                        f"{attempt['label']} scrape {url}: {scrape_error}"
                    )
                    continue
                markdown = _extract_scrape_markdown(scrape_result).strip()
                if not markdown:
                    continue
                scraped_data.append(
                    {
                        "url": url,
                        "content": markdown[:MAX_SCRAPE_CHARS],
                    }
                )

            if scraped_data:
                try:
                    firecrawl_summary = _summarize_scraped_pages(state, scraped_data)
                except Exception as summary_error:
                    logger.error(
                        f"Failed to summarize scraped Firecrawl content: {summary_error}"
                    )
                    attempt_errors.append(
                        f"{attempt['label']} summary: {summary_error}"
                    )

            # Rerank with ReLU
            ranked_items = rerank_with_relu(
                query,
                raw_items,
                lambda row: " ".join(
                    [
                        str(row.get("title", "")),
                        str(row.get("markdown", ""))[:1000],
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
                        "source": f"Firecrawl {attempt['label']}",
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "claim": (
                            (matching_scrape or {}).get("content")
                            or item.get("markdown", "")
                            or item.get("title", "")
                        )[:500],
                        "type": "web",
                        "confidence": min(0.99, 0.62 + (relu_score / 5.5)),
                        "provider": "firecrawl",
                        "relu_score": relu_score,
                    }
                )

            active_mode = attempt["label"]
            logger.info(f"Deep research found {len(evidence)} items via {active_mode}")

            if evidence:
                break

        except Exception as attempt_error:
            error_msg = f"{attempt['label']}: {attempt_error}"
            attempt_errors.append(error_msg)
            logger.error(f"Firecrawl attempt failed: {error_msg}")

    return {
        "evidence": evidence,
        "scraped_data": scraped_data,
        "firecrawl_summary": firecrawl_summary,
        "current_task": f"Deep research: {len(evidence)} pages crawled",
        "thinking_log": [
            {
                "node": "deep_research",
                "title": "Firecrawl deep research completed"
                if evidence
                else "Firecrawl deep research failed",
                "detail": (
                    f"Used {active_mode or 'configured'} Firecrawl, scraped {len(scraped_data)} pages, and reranked {len(evidence)} pages with ReLU."
                    if evidence
                    else "Firecrawl could not return deep crawl pages. "
                    + (
                        " | ".join(attempt_errors)
                        if attempt_errors
                        else "No results returned."
                    )
                ),
                "provider": "firecrawl",
                "mode": active_mode or config.get("strategy", "self_hosted_first"),
                "result_count": len(evidence),
            }
        ],
    }
