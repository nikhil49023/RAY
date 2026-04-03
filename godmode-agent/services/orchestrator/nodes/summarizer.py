"""
summarizer.py – Phase 4: Rolling Context Compressor
----------------------------------------------------
Triggered every SUMMARIZE_EVERY_N_TURNS turns (or when token estimate
exceeds TOKEN_THRESHOLD).  Compresses the full message history into a
structured 4-part summary and slides the recent_messages window.

Summary format (returned in state['session_summary']):
    Goal      : <what the user is ultimately trying to achieve>
    Decisions : <key choices already made>
    Facts     : <verified facts established during the session>
    Open      : <unresolved questions / next steps>
"""

from __future__ import annotations

import time
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.state import AgentState

# ──────────────────────────────────────────────────────────────────────────── #
# Configuration                                                                #
# ──────────────────────────────────────────────────────────────────────────── #

SUMMARIZE_EVERY_N_TURNS: int = 6        # hard turn-based trigger
TOKEN_THRESHOLD: int = 4_000            # rough token estimate threshold
RECENT_WINDOW: int = 6                  # how many messages to keep verbatim
AVG_CHARS_PER_TOKEN: float = 3.8        # used for cheap token estimation

# Configuration
# ──────────────────────────────────────────────────────────────────────────── #


_SYSTEM_PROMPT = """\
You are a Conversation Distiller for a God-Mode Agent context pipeline.

Given the conversation history below, produce a concise 4-part structured
summary in EXACTLY this format (one sentence per field – be dense):

Goal      : <the user's overarching objective>
Decisions : <key choices or answers already established>
Facts     : <verified facts / data points surfaced so far>
Open      : <open questions or next steps still pending>

Be ruthlessly concise. Each field should be ≤ 40 words.
Do NOT add any extra text or markdown outside the four fields.
"""


# ──────────────────────────────────────────────────────────────────────────── #
# Helpers                                                                      #
# ──────────────────────────────────────────────────────────────────────────── #

def _estimate_tokens(messages: List[BaseMessage]) -> int:
    """Rough token count based on character length."""
    total_chars = sum(len(m.content) for m in messages)
    return int(total_chars / AVG_CHARS_PER_TOKEN)


def _should_summarize(state: AgentState) -> bool:
    """Return True if either trigger condition is met."""
    turn_count = state.get("turn_count", 0)
    messages   = state.get("messages", [])

    if turn_count > 0 and turn_count % SUMMARIZE_EVERY_N_TURNS == 0:
        return True

    if _estimate_tokens(messages) >= TOKEN_THRESHOLD:
        return True

    return False


def _build_history_text(messages: List[BaseMessage]) -> str:
    lines = []
    for m in messages:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        lines.append(f"{role}: {m.content[:800]}")   # cap per-message chars
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────── #
# Node                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #

def summarizer(state: AgentState) -> dict:
    """
    LangGraph node: compresses conversation history when triggered.
    Uses the user-selected brain for compression.
    """
    t0 = time.perf_counter()
    messages: List[BaseMessage] = state.get("messages", [])
    
    # Use selected brain for summarization to maintain unified model logic
    selected_brain = state.get("selected_model", "sarvam/sarvam-105b")
    llm = LLMFactory.get_model(role="summarizer", temperature=0.1, max_tokens=600, model_id=selected_brain)

    # Always slide the recent_messages window regardless of trigger
    recent_messages = messages[-RECENT_WINDOW:] if len(messages) > RECENT_WINDOW else messages

    if not _should_summarize(state):
        # No compression needed – just update the window
        return {
            "recent_messages": recent_messages,
            "current_task": "Context Window Maintained",
        }

    # ── Compress ──────────────────────────────────────────────────────────── #
    existing_summary = state.get("session_summary", "")
    history_text     = _build_history_text(messages)

    # Prepend prior summary so we don't lose older context
    user_block = (
        f"[Previous Summary]\n{existing_summary}\n\n[New Messages]\n{history_text}"
        if existing_summary
        else history_text
    )

    try:
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_block),
        ])
        new_summary = response.content.strip()
    except Exception as exc:
        # Graceful degradation – keep old summary, log warning
        print(f"[summarizer] LLM call failed: {exc}")
        new_summary = existing_summary or ""

    elapsed = time.perf_counter() - t0

    return {
        "session_summary":  new_summary,
        "recent_messages":  recent_messages,
        "current_task":     "Context Compressed",
        "node_timings":     {**state.get("node_timings", {}), "summarizer": round(elapsed, 3)},
    }
