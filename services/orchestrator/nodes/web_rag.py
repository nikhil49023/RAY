from pathlib import Path
import sys
import re

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings
from services.orchestrator.state import AgentState

try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False


def _extract_urls(text: str) -> list:
    """Extract URLs from text."""
    pattern = re.compile(r"https?://[^\s]+", flags=re.IGNORECASE)
    return pattern.findall(text)


def web_rag(state: AgentState) -> AgentState:
    """Scrape web pages using Firecrawl."""
    
    if not FIRECRAWL_AVAILABLE:
        state["web_rag_results"] = []
        return state
    
    # Extract URLs from query
    urls = _extract_urls(state["user_query"])
    
    if not urls:
        state["web_rag_results"] = []
        return state
    
    try:
        app = FirecrawlApp(
            api_key=settings.firecrawl_api_key,
            api_url=settings.firecrawl_base_url
        )
        
        results = []
        for url in urls[:3]:  # Limit to 3 URLs
            try:
                scraped = app.scrape_url(url, params={"formats": ["markdown"]})
                results.append({
                    "content": scraped.get("markdown", ""),
                    "url": url,
                    "source": "firecrawl"
                })
            except Exception:
                continue
        
        state["web_rag_results"] = results
        
    except Exception as e:
        state["web_rag_results"] = []
        if not state.get("error"):
            state["error"] = f"Firecrawl error: {str(e)}"
    
    return state
