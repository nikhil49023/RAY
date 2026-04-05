from __future__ import annotations

from langchain_core.messages import HumanMessage

from services.orchestrator.nodes.deep_research_rag import deep_research_rag


def test_deep_research_scrapes_candidate_urls_and_summarizes(monkeypatch):
    class FakeScrapeResult:
        def __init__(self, markdown: str):
            self.markdown = markdown

    class FakeFirecrawlApp:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def search(self, **kwargs):
            return {
                "data": [
                    {"title": "Firecrawl", "url": "https://firecrawl.dev", "markdown": "Firecrawl home"},
                    {"title": "Pricing", "url": "https://firecrawl.dev/pricing", "markdown": "Pricing page"},
                ]
            }

        def scrape_url(self, url, **kwargs):
            return FakeScrapeResult(f"Scraped content for {url}")

    captured: dict[str, object] = {}

    class FakeLLM:
        def invoke(self, messages):
            captured["messages"] = messages
            return type("FakeResponse", (), {"content": "## Executive Summary\nSummary\n## Key Findings\n- A\n## Important URLs\n- https://firecrawl.dev"})()

    monkeypatch.setattr("services.orchestrator.nodes.deep_research_rag.load_user_settings", lambda: {})
    monkeypatch.setattr(
        "services.orchestrator.nodes.deep_research_rag.get_firecrawl_config",
        lambda settings=None: {
            "strategy": "self_hosted_first",
            "base_url": "http://localhost:3002",
            "cloud_url": "https://api.firecrawl.dev",
            "fallback_api_key": "",
        },
    )
    monkeypatch.setattr("services.orchestrator.nodes.deep_research_rag._is_firecrawl_healthy", lambda api_url: (True, ""))
    monkeypatch.setattr("services.orchestrator.nodes.deep_research_rag.rerank_with_relu", lambda query, rows, extractor: rows)
    def fake_get_model(**kwargs):
        captured["model_id"] = kwargs["model_id"]
        return FakeLLM()

    monkeypatch.setattr("services.orchestrator.nodes.deep_research_rag.LLMFactory.get_model", fake_get_model)
    monkeypatch.setattr("firecrawl.FirecrawlApp", FakeFirecrawlApp)

    result = deep_research_rag({
        "messages": [HumanMessage(content="Research Firecrawl pricing")],
        "rewritten_query": "Research Firecrawl pricing",
        "research_level": "deep",
        "selected_model": "groq/llama-3.3-70b-versatile",
        "temperature": 0.1,
        "evidence": [
            {"url": "https://firecrawl.dev", "title": "Firecrawl"},
            {"url": "https://firecrawl.dev/pricing", "title": "Pricing"},
        ],
    })

    assert len(result["scraped_data"]) == 2
    assert result["scraped_data"][0]["url"] == "https://firecrawl.dev"
    assert "Scraped content for https://firecrawl.dev" in result["scraped_data"][0]["content"]
    assert result["firecrawl_summary"].startswith("## Executive Summary")
    assert len(result["evidence"]) == 2
    assert captured["model_id"] == "groq/openai/gpt-oss-20b"
    assert "https://firecrawl.dev" in str(captured["messages"][-1].content)
