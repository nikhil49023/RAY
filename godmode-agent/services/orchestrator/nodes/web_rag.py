"""
web_rag.py — DuckDuckGo Web Search
------------------------------------
Lightweight web search for basic research.
Skips if research_level is 'none'.
"""

from services.orchestrator.state import AgentState
from services.orchestrator.relevance import rerank_with_relu

try:
    from ddgs import DDGS  # type: ignore
except ImportError:
    from duckduckgo_search import DDGS  # type: ignore


def web_rag(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    research_level = state.get("research_level", "basic")

    if research_level == "none":
        return {
            "evidence": [],  # Always return evidence key to avoid merge error
            "current_task": "Web search skipped (reasoning mode)",
            "thinking_log": [{
                "node": "web_rag",
                "title": "Web search skipped",
                "detail": "Reasoning mode disabled external web search.",
                "provider": "duckduckgo",
            }],
        }

    evidence = []
    try:
        max_results = 5 if research_level == "deep" else 3
        raw_results = list(DDGS().text(query, max_results=max_results))
        ranked_results = rerank_with_relu(
            query,
            raw_results,
            lambda row: " ".join([
                str(row.get("title", "")),
                str(row.get("body", "")),
                str(row.get("href", "")),
            ]),
        )
        for r in ranked_results[:max_results]:
            relu_score = float(r.get("relu_score", 0.0))
            evidence.append({
                "source": "DuckDuckGo",
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "claim": r.get("body", ""),
                "type": "web",
                "confidence": min(0.97, 0.55 + (relu_score / 5.0)),
                "provider": "duckduckgo",
                "relu_score": relu_score,
            })
    except Exception as e:
        print(f"[web_rag] DuckDuckGo error: {e}")
        return {
            "evidence": evidence,
            "current_task": "Web search failed",
            "thinking_log": [{
                "node": "web_rag",
                "title": "DuckDuckGo search failed",
                "detail": f"DuckDuckGo could not return results: {e}",
                "provider": "duckduckgo",
                "reranker": "ReLU",
            }],
        }

    return {
        "evidence": evidence,
        "current_task": f"Web search: {len(evidence)} results",
        "thinking_log": [{
            "node": "web_rag",
            "title": "DuckDuckGo results reranked",
            "detail": f"Fetched {len(evidence)} web results and reranked them with ReLU precision scoring.",
            "provider": "duckduckgo",
            "reranker": "ReLU",
            "result_count": len(evidence),
        }],
    }
