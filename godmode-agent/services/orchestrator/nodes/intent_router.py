"""
intent_router.py — Intent Classification & Query Rewriting
-----------------------------------------------------------
1. Rewrites the raw query using session_summary for coreference resolution.
2. Classifies intent: chat | research | coding | artifact
3. Increments turn_count.

LLM resolution is lazy so tests can patch the shared handle.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory

# Configure logging
logger = logging.getLogger("ray.intent_router")

# ── Prompts ───────────────────────────────────────────────────────────────── #

_REWRITE_SYSTEM = """\
You are a Query Rewriter. Given a rolling session summary and the user's latest
message, rewrite it into a SELF-CONTAINED question (resolve pronouns, expand
implicit references). If it already stands alone, return it unchanged.
Keep ≤ 60 words. Return ONLY the rewritten query.
"""

_CLASSIFY_SYSTEM = """\
Classify the user message into exactly ONE category. Reply with the word only.

Categories:
- chat           (general conversation, opinion, explanation, simple Q&A)
- research       (needs analysis, current facts, evidence, or technical investigation)
- canvas         (draft, write, create, format, or edit a document/report)
- memory_recall  (asking about previous conversations, saved research, or past documents)

If the request is about coding or debugging, classify it as research.
If uncertain, pick research for technical/analytical tasks, chat otherwise.
"""


# Test harnesses patch this directly; production resolves lazily from state.
llm: Any = None


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _resolve_llm(state: AgentState) -> Any:
    if llm is not None:
        return llm
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")
    return LLMFactory.get_model(model_id=model_id, temperature=0.0)


# ── Node ──────────────────────────────────────────────────────────────────── #

def intent_router(state: AgentState) -> dict:
    """Classify intent and rewrite query. Uses the user-selected brain."""
    raw_query = _message_text(state["messages"][-1].content)
    session_summary = state.get("session_summary")
    resolved_llm = _resolve_llm(state)

    logger.debug(f"Processing query: {raw_query[:50]}...")

    # ── Rewrite ───────────────────────────────────────────────────────────
    rewritten = raw_query
    if session_summary:
        try:
            resp = resolved_llm.invoke([
                SystemMessage(content=_REWRITE_SYSTEM),
                HumanMessage(content=f"[Summary]\n{session_summary}\n\n[Message]\n{raw_query}"),
            ])
            rewritten = _message_text(resp.content).strip() or raw_query
            logger.debug(f"Rewritten query: {rewritten[:50]}...")
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")

    # ── Classify ──────────────────────────────────────────────────────────
    try:
        resp = resolved_llm.invoke([
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=rewritten),
        ])
        intent = _message_text(resp.content).strip().lower()
        if intent == "artifact":
            intent = "canvas"
        elif intent == "coding":
            intent = "research"
        if intent not in {"chat", "research", "canvas", "memory_recall"}:
            intent = "chat"
        logger.info(f"Classified intent: {intent}")
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
        intent = "chat"

    turn_count = state.get("turn_count", 0) + 1

    return {
        "intent": intent,
        "rewritten_query": rewritten,
        "turn_count": turn_count,
        "current_task": f"Intent: {intent}",
    }
