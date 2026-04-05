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
from requests.exceptions import RequestException, Timeout, ConnectionError

from services.orchestrator.state import AgentState
from services.orchestrator.relevance import rerank_with_relu
from services.orchestrator.runtime import get_firecrawl_config, load_user_settings

# Configure logging
logger = logging.getLogger("ray.deep_research")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff delays in seconds
REQUEST_TIMEOUT = 30  # seconds


def _extract_firecrawl_items(result) -> list:
    if isinstance(result, dict):
        data = result.get("data")
        return data if isinstance(data, list) else []
    data = getattr(result, "data", None)
    return data if isinstance(data, list) else []


def _is_firecrawl_healthy(api_url: str) -> Tuple[bool, str]:
    """Check if Firecrawl endpoint is healthy with timeout."""
    try:
        response = requests.get(
            f"{api_url.rstrip('/')}/health",
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            return True, ""
        return False, f"health check returned {response.status_code}"
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
            "thinking_log": [{
                "node": "deep_research",
                "title": "Firecrawl unavailable",
                "detail": "No self-hosted Firecrawl URL or cloud fallback key is configured.",
                "provider": "firecrawl",
            }],
        }

    # Build attempts list based on strategy
    attempts: List[Dict[str, str]] = []
    if base_url and strategy != "cloud_only":
        attempts.append({
            "label": "self-hosted",
            "api_url": base_url,
            "api_key": "",
        })
    if fallback_key:
        attempts.append({
            "label": "cloud-fallback",
            "api_url": cloud_url,
            "api_key": fallback_key,
        })

    attempt_errors: List[str] = []
    active_mode = ""

    try:
        from firecrawl import FirecrawlApp
    except ImportError as e:
        logger.error("Firecrawl package not installed")
        return {
            "evidence": [],
            "current_task": "Deep research: Firecrawl not installed",
            "thinking_log": [{
                "node": "deep_research",
                "title": "Firecrawl unavailable",
                "detail": "Firecrawl package is not installed. Run: pip install firecrawl-py",
                "provider": "firecrawl",
            }],
        }

    for attempt in attempts:
        try:
            logger.info(f"Trying {attempt['label']} Firecrawl endpoint...")

            # Health check for self-hosted
            if attempt["label"] == "self-hosted":
                healthy, health_error = _is_firecrawl_healthy(attempt["api_url"])
                if not healthy:
                    attempt_errors.append(f"{attempt['label']}: unavailable ({health_error})")
                    logger.warning(f"Health check failed for {attempt['label']}: {health_error}")
                    continue

            # Initialize Firecrawl client
            kwargs: Dict[str, str] = {}
            if attempt["api_url"]:
                kwargs["api_url"] = attempt["api_url"]
            if attempt["api_key"]:
                kwargs["api_key"] = attempt["api_key"]

            app = FirecrawlApp(**kwargs)
            if not hasattr(app, "search"):
                attempt_errors.append(f"{attempt['label']}: installed Firecrawl client has no search() method")
                logger.error(f"Firecrawl client missing search method for {attempt['label']}")
                continue

            # Perform search with retry logic
            success, result, error = _retry_with_backoff(
                app.search,
                kwargs={"query": query, "limit": 8}
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

            logger.info(f"Retrieved {len(raw_items)} raw results from {attempt['label']}")

            # Rerank with ReLU
            ranked_items = rerank_with_relu(
                query,
                raw_items,
                lambda row: " ".join([
                    str(row.get("title", "")),
                    str(row.get("markdown", ""))[:1000],
                    str(row.get("url", "")),
                ]),
            )

            for item in ranked_items[:8]:
                relu_score = float(item.get("relu_score", 0.0))
                evidence.append({
                    "source": f"Firecrawl {attempt['label']}",
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "claim": (item.get("markdown", "") or item.get("title", ""))[:500],
                    "type": "web",
                    "confidence": min(0.99, 0.62 + (relu_score / 5.5)),
                    "provider": "firecrawl",
                    "relu_score": relu_score,
                })

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
        "current_task": f"Deep research: {len(evidence)} pages crawled",
        "thinking_log": [{
            "node": "deep_research",
            "title": "Firecrawl deep research completed" if evidence else "Firecrawl deep research failed",
            "detail": (
                f"Used {active_mode or 'configured'} Firecrawl and reranked {len(evidence)} pages with ReLU."
                if evidence
                else "Firecrawl could not return deep crawl pages. " + (" | ".join(attempt_errors) if attempt_errors else "No results returned.")
            ),
            "provider": "firecrawl",
            "mode": active_mode or config.get("strategy", "self_hosted_first"),
            "result_count": len(evidence),
        }],
    }
