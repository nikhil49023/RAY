from pathlib import Path
import sys
import re

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.api_handlers import MultiProviderClients
from services.orchestrator.state import AgentState


def _extract_urls(text: str) -> list:
    """Extract URLs from text."""
    pattern = re.compile(r"https?://[^\s]+", flags=re.IGNORECASE)
    return pattern.findall(text)


def web_rag(state: AgentState) -> AgentState:
    """Discover candidate URLs with DuckDuckGo and scrape via Firecrawl."""

    query = str(state.get("user_query", "")).strip()
    if not query:
        state["web_rag_results"] = []
        return state

    client = MultiProviderClients()
    urls = _extract_urls(query)

    if not urls:
        try:
            search_results = client.search_web(query, max_results=3)
            urls = [item.get("url", "") for item in search_results if item.get("url")]
        except Exception:
            urls = []

    if not urls:
        state["web_rag_results"] = []
        return state

    results = []
    errors = []
    for url in urls[:3]:
        try:
            scraped = client.scrape_url(url)
            markdown = str(
                scraped.get("markdown") or scraped.get("content") or ""
            ).strip()
            if markdown:
                results.append(
                    {
                        "content": markdown,
                        "url": url,
                        "source": "firecrawl",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    state["web_rag_results"] = results
    if errors and not results and not state.get("error"):
        state["error"] = "Web RAG failed: " + " | ".join(errors)

    return state
