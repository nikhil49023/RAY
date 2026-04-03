"""
intent_router.py — Intent Classification & Query Rewriting
-----------------------------------------------------------
1. Rewrites the raw query using session_summary for coreference resolution.
2. Classifies intent: chat | research | coding | artifact
3. Increments turn_count.

NO module-level LLM instantiation.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory

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
- chat        (casual conversation, greetings, simple Q&A)
- research    (scientific, academic, tech questions needing evidence)
- coding      (write/debug code, scripts, algorithms)
- artifact    (generate documents, reports, essays, diagrams)

If uncertain, pick "research" for science/tech topics, "chat" otherwise.
"""


# ── Node ──────────────────────────────────────────────────────────────────── #

def intent_router(state: AgentState) -> dict:
    """Classify intent and rewrite query. Uses the user-selected brain."""
    raw_query = state["messages"][-1].content
    session_summary = state.get("session_summary")
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")

    llm = LLMFactory.get_model(model_id=model_id, temperature=0.0)

    # ── Rewrite ───────────────────────────────────────────────────────────
    rewritten = raw_query
    if session_summary:
        try:
            resp = llm.invoke([
                SystemMessage(content=_REWRITE_SYSTEM),
                HumanMessage(content=f"[Summary]\n{session_summary}\n\n[Message]\n{raw_query}"),
            ])
            rewritten = resp.content.strip() or raw_query
        except Exception as e:
            print(f"[intent_router] Rewrite failed: {e}")

    # ── Classify ──────────────────────────────────────────────────────────
    try:
        resp = llm.invoke([
            SystemMessage(content=_CLASSIFY_SYSTEM),
            HumanMessage(content=rewritten),
        ])
        intent = resp.content.strip().lower()
        if intent not in {"chat", "research", "coding", "artifact"}:
            intent = "chat"
    except Exception as e:
        print(f"[intent_router] Classification failed: {e}")
        intent = "chat"

    turn_count = state.get("turn_count", 0) + 1

    return {
        "intent": intent,
        "rewritten_query": rewritten,
        "turn_count": turn_count,
        "current_task": f"Intent: {intent}",
    }
