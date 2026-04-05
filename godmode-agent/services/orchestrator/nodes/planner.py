"""
planner.py — Task Planner
--------------------------
Generates a structured execution plan. Determines research_level.
Uses the user-selected brain.
"""

import logging
import re

from langchain_core.messages import SystemMessage, HumanMessage
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.runtime import load_user_settings
from services.orchestrator.visual_output import build_visual_output_guidance

# Configure logging
logger = logging.getLogger("ray.planner")


def planner(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["messages"][-1].content
    intent = state.get("intent", "research")
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")
    memory_context = state.get("memory_context", "")
    settings = load_user_settings()
    ui_settings = settings.get("ui", {})
    temperature = float(state.get("temperature", settings.get("temperature", 0.1)))
    visuals_enabled = bool(state.get("visuals_enabled", ui_settings.get("renderVisualsInline", False)))

    logger.info(f"Planning for intent={intent}, model={model_id}")

    try:
        llm = LLMFactory.get_model(model_id=model_id, temperature=temperature)
    except Exception as e:
        logger.error(f"Failed to initialize LLM for planning: {e}")
        # Return a safe default plan
        return {
            "plan": f"Error: Could not initialize model. {e}",
            "research_level": "basic",
            "current_task": "Planning error",
            "thinking_log": [{
                "node": "planner",
                "title": "Planning failed",
                "detail": f"Model initialization failed: {e}",
                "mode": state.get("agent_mode", "standard"),
                "research_level": "basic",
            }],
        }

    output_features = build_visual_output_guidance(visuals_enabled=visuals_enabled)

    system_prompt = f"""\
You are a Scientific Task Planner for an AI research assistant.
Domain focus: Education, Science, Technology.
User intent: {intent}

Available tools:
0. Semantic memory retrieval — prior conversations, saved research, user preferences
1. Web Search (DuckDuckGo) — quick fact-checking, current events
2. Self-Hosted Firecrawl — deep domain crawling, full-page extraction
3. Document RAG — internal knowledge retrieval (when available)
4. ReLU reranker — precision-oriented reranking for DDG + Firecrawl evidence

{output_features}

Produce a plan with these sections:
1. SUBTASKS: numbered steps
2. TOOLS: which tools to use
3. RESEARCH_DEPTH: exactly one of [none, basic, deep]
   - none: simple chat, no web search needed
   - basic: DuckDuckGo search sufficient
   - deep: Firecrawl crawl + extensive web search

Be concise. No filler."""

    try:
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Retrieved memory context:\n{memory_context or 'None'}\n\nUser query:\n{query}"),
        ])
        content = resp.content
        logger.debug(f"Planner response received ({len(str(content))} chars)")
    except Exception as e:
        logger.error(f"LLM invocation failed in planner: {e}")
        content = "Planning failed due to model error."
        research_level = "basic"
        mode = state.get("agent_mode", "standard")
        return {
            "plan": content,
            "research_level": research_level,
            "current_task": "Planning error",
            "thinking_log": [{
                "node": "planner",
                "title": "Planning failed",
                "detail": f"LLM error: {e}",
                "mode": mode,
                "research_level": research_level,
            }],
        }

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
    elif intent == "memory_recall":
        research_level = "none"

    plan_summary = " ".join(line.strip() for line in content.splitlines() if line.strip())[:300]

    logger.info(f"Plan complete - research_level={research_level}, mode={mode}")

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
            "visuals_enabled": visuals_enabled,
        }],
    }
