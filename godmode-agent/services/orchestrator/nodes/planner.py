"""
planner.py — Task Planner
--------------------------
Generates a structured execution plan. Determines research_level.
Uses the user-selected brain.
"""

import re
from langchain_core.messages import SystemMessage, HumanMessage
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.runtime import load_user_settings


def planner(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    intent = state.get("intent", "research")
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")
    settings = load_user_settings()
    ui_settings = settings.get("ui", {})
    temperature = float(state.get("temperature", settings.get("temperature", 0.1)))

    llm = LLMFactory.get_model(model_id=model_id, temperature=temperature)

    system_prompt = f"""\
You are a Scientific Task Planner for an AI research assistant.
Domain focus: Education, Science, Technology.
User intent: {intent}

Available tools:
1. Web Search (DuckDuckGo) — quick fact-checking, current events
2. Self-Hosted Firecrawl — deep domain crawling, full-page extraction
3. Document RAG — internal knowledge retrieval (when available)
4. ReLU reranker — precision-oriented reranking for DDG + Firecrawl evidence

Output features:
- Research documents — wrap detailed research output in <document: title>…</document> tags
- Canvas documents — wrap long-form drafts in <canvas: title>…</canvas> tags
- Charts — use ```chart JSON blocks for rankings, trends, or comparisons
- Mermaid diagrams — use ```mermaid code blocks for flowcharts/diagrams

Produce a plan with these sections:
1. SUBTASKS: numbered steps
2. TOOLS: which tools to use
3. RESEARCH_DEPTH: exactly one of [none, basic, deep]
   - none: simple chat, no web search needed
   - basic: DuckDuckGo search sufficient
   - deep: Firecrawl crawl + extensive web search

Be concise. No filler."""

    resp = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ])
    content = resp.content

    # Extract research depth
    research_level = "basic"
    m = re.search(r"RESEARCH_DEPTH:\s*\[?(none|basic|deep)\]?", content, re.IGNORECASE)
    if m:
        research_level = m.group(1).lower()

    # UI mode overrides
    mode = state.get("agent_mode", "standard")
    if mode == "research":
        research_level = "deep"
    elif mode == "reasoning":
        research_level = "none"  # reasoning = no web, just think

    plan_summary = " ".join(line.strip() for line in content.splitlines() if line.strip())[:300]

    return {
        "plan": content,
        "research_level": research_level,
        "current_task": "Planning complete",
        "thinking_log": [{
            "node": "planner",
            "title": "Research plan prepared",
            "detail": plan_summary or "Planner generated a structured route for this request.",
            "mode": mode,
            "research_level": research_level,
            "research_output": ui_settings.get("researchOutput", "document"),
        }],
    }
