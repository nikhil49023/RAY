"""
deep_research_rag.py — Firecrawl Deep Research
------------------------------------------------
Deep domain crawling using self-hosted Firecrawl.
Only runs when research_level == 'deep'.
"""

from services.orchestrator.state import AgentState
from services.orchestrator.relevance import rerank_with_relu
from services.orchestrator.runtime import get_firecrawl_config, load_user_settings


def deep_research_rag(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    research_level = state.get("research_level", "basic")

    if research_level != "deep":
        return {"evidence": [], "current_task": "Deep research skipped"}

    evidence = []
    settings = load_user_settings()
    config = get_firecrawl_config(settings)
    base_url = config.get("base_url", "")
    cloud_url = config.get("cloud_url", "")
    fallback_key = config.get("fallback_api_key", "")
    strategy = config.get("strategy", "self_hosted_first")

    if not base_url and not fallback_key:
        return {
            "evidence": [{
                "source": "System",
                "claim": "Firecrawl not configured. Set a self-host URL or fallback API key in Settings.",
                "type": "error",
                "confidence": 0.0,
            }],
            "current_task": "Deep research: not configured",
            "thinking_log": [{
                "node": "deep_research",
                "title": "Firecrawl unavailable",
                "detail": "No self-hosted Firecrawl URL or cloud fallback key is configured.",
                "provider": "firecrawl",
            }],
        }

    attempts = []
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

    attempt_errors = []
    active_mode = ""
    try:
        from firecrawl import FirecrawlApp

        for attempt in attempts:
            try:
                kwargs = {}
                if attempt["api_url"]:
                    kwargs["api_url"] = attempt["api_url"]
                if attempt["api_key"]:
                    kwargs["api_key"] = attempt["api_key"]

                app = FirecrawlApp(**kwargs)
                result = app.search(query=query)
                raw_items = result.get("data", []) if isinstance(result, dict) else []
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
                if evidence:
                    break
            except Exception as attempt_error:
                attempt_errors.append(f"{attempt['label']}: {attempt_error}")
    except Exception as e:
        print(f"[deep_research_rag] Firecrawl error: {e}")
        evidence.append({
            "source": "Firecrawl",
            "claim": f"Crawl failed: {e}",
            "type": "error",
            "confidence": 0.0,
        })
        attempt_errors.append(str(e))

    if not evidence and attempt_errors:
        evidence.append({
            "source": "Firecrawl",
            "claim": " | ".join(attempt_errors),
            "type": "error",
            "confidence": 0.0,
        })

    return {
        "evidence": evidence,
        "current_task": f"Deep research: {len(evidence)} pages crawled",
        "thinking_log": [{
            "node": "deep_research",
            "title": "Firecrawl deep research completed" if evidence else "Firecrawl deep research failed",
            "detail": (
                f"Used {active_mode or 'configured'} Firecrawl and reranked {len(evidence)} pages with ReLU."
                if evidence
                else "Firecrawl could not return deep crawl pages. " + " | ".join(attempt_errors)
            ),
            "provider": "firecrawl",
            "mode": active_mode or config.get("strategy", "self_hosted_first"),
            "result_count": len(evidence),
        }],
    }
