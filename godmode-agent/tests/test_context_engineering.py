"""
tests/test_context_engineering.py
----------------------------------
Unit tests for the Layered Context Pipeline (Phase 4).

Verifies:
  1. summarizer triggers at the correct turn count (every N turns).
  2. summarizer triggers when estimated token count exceeds threshold.
  3. summarizer skips compression when neither condition is met.
  4. session_summary is correctly prepended to the next summarization call.
  5. recent_messages window never exceeds RECENT_WINDOW.
  6. intent_router increments turn_count on each invocation.
  7. intent_router rewrites queries using the session_summary context
     (mocked LLM call).
  8. intent_router falls back to raw query when rewrite LLM fails.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_messages(n: int):
    msgs = []
    for i in range(n):
        msgs.append(HumanMessage(content=f"User message {i}: " + "x" * 50))
        msgs.append(AIMessage(content=f"Assistant reply {i}: " + "x" * 50))
    return msgs


def _base_state(**kwargs):
    defaults = dict(
        messages          = [],
        session_summary   = None,
        recent_messages   = [],
        applied_rules     = [],
        turn_count        = 0,
        intent            = None,
        rewritten_query   = None,
        plan              = None,
        evidence          = [],
        behavioral_memories = [],
        verification_status = "PENDING",
        artifacts         = [],
        current_task      = None,
        completed_nodes   = [],
        node_timings      = {},
        telemetry         = {},
        errors            = [],
    )
    defaults.update(kwargs)
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# Summarizer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSummarizer:

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_triggers_every_n_turns(self, mock_llm):
        """Compression runs when turn_count is a multiple of SUMMARIZE_EVERY_N_TURNS."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        mock_llm.invoke.return_value = MagicMock(content=(
            "Goal: test | Decisions: none | Facts: none | Open: nothing"
        ))

        state = _base_state(
            messages   = _make_messages(5),
            turn_count = SUMMARIZE_EVERY_N_TURNS,   # exactly on trigger
        )
        result = summarizer(state)

        assert "session_summary" in result
        assert result["session_summary"] != ""
        mock_llm.invoke.assert_called_once()

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_no_trigger_mid_cycle(self, mock_llm):
        """No compression between trigger points."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        state = _base_state(
            messages   = _make_messages(2),
            turn_count = SUMMARIZE_EVERY_N_TURNS - 1,
        )
        result = summarizer(state)

        mock_llm.invoke.assert_not_called()
        assert "session_summary" not in result or result.get("session_summary") is None

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_triggers_on_token_threshold(self, mock_llm):
        """Compression fires when estimated token count is over threshold."""
        from services.orchestrator.nodes.summarizer import (
            summarizer, TOKEN_THRESHOLD, AVG_CHARS_PER_TOKEN
        )

        mock_llm.invoke.return_value = MagicMock(content="Goal: big session | Decisions: many | Facts: lots | Open: more")

        # Build messages that exceed token threshold
        chars_needed = int(TOKEN_THRESHOLD * AVG_CHARS_PER_TOKEN) + 100
        big_message  = HumanMessage(content="x" * chars_needed)
        state        = _base_state(messages=[big_message], turn_count=1)

        result = summarizer(state)
        assert result.get("session_summary"), "Expected a summary to be generated"
        mock_llm.invoke.assert_called_once()

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_prepends_existing_summary(self, mock_llm):
        """Existing session_summary is included in the next LLM call."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        old_summary = "Goal: old | Decisions: done | Facts: known | Open: nothing"
        mock_llm.invoke.return_value = MagicMock(content="Goal: new | Decisions: updated | Facts: fresh | Open: tbd")

        state = _base_state(
            messages        = _make_messages(3),
            session_summary = old_summary,
            turn_count      = SUMMARIZE_EVERY_N_TURNS,
        )
        summarizer(state)

        call_args = mock_llm.invoke.call_args
        prompt_content = str(call_args)
        assert "old" in prompt_content or old_summary[:20] in prompt_content

    def test_recent_messages_window_capped(self):
        """recent_messages should never exceed RECENT_WINDOW items."""
        from services.orchestrator.nodes.summarizer import summarizer, RECENT_WINDOW

        state = _base_state(messages=_make_messages(20), turn_count=1)

        with patch("services.orchestrator.nodes.summarizer._llm"):
            result = summarizer(state)

        assert len(result["recent_messages"]) <= RECENT_WINDOW

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_graceful_llm_failure(self, mock_llm):
        """Keeps old summary if LLM call raises an exception."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
        old_summary = "Goal: survive | Decisions: none | Facts: llm down | Open: retry"

        state = _base_state(
            messages        = _make_messages(5),
            session_summary = old_summary,
            turn_count      = SUMMARIZE_EVERY_N_TURNS,
        )
        result = summarizer(state)

        # Should not raise; old summary preserved
        assert result.get("session_summary") == old_summary


# ─────────────────────────────────────────────────────────────────────────────
# Intent router / query rewriting tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentRouter:

    @patch("services.orchestrator.nodes.intent_router.llm")
    def test_turn_count_increments(self, mock_llm):
        """turn_count must increase by 1 on each router invocation."""
        from services.orchestrator.nodes.intent_router import intent_router

        mock_llm.invoke.return_value = MagicMock(content="chat")
        state = _base_state(messages=[HumanMessage(content="hello")], turn_count=3)

        result = intent_router(state)
        assert result["turn_count"] == 4

    @patch("services.orchestrator.nodes.intent_router.llm")
    def test_query_rewrite_uses_summary(self, mock_llm):
        """rewritten_query is the rewrite output when summary is present."""
        from services.orchestrator.nodes.intent_router import intent_router

        rewritten = "What is the status of the SUTRA drone's IMU calibration?"
        # First call = rewrite, second call = classify
        mock_llm.invoke.side_effect = [
            MagicMock(content=rewritten),
            MagicMock(content="research"),
        ]

        state = _base_state(
            messages        = [HumanMessage(content="What about the IMU?")],
            session_summary = "Goal: calibrate SUTRA IMU | Decisions: use BNO085 | Facts: none | Open: pending",
        )
        result = intent_router(state)

        assert result["rewritten_query"] == rewritten
        assert result["intent"] == "research"

    @patch("services.orchestrator.nodes.intent_router.llm")
    def test_no_rewrite_without_summary(self, mock_llm):
        """When session_summary is None, raw query is passed through unchanged."""
        from services.orchestrator.nodes.intent_router import intent_router

        raw = "What is the weather?"
        mock_llm.invoke.return_value = MagicMock(content="chat")

        state = _base_state(messages=[HumanMessage(content=raw)])
        result = intent_router(state)

        # Rewrite LLM should NOT be called (no summary)
        assert result["rewritten_query"] == raw
        mock_llm.invoke.assert_called_once()   # only the classify call

    @patch("services.orchestrator.nodes.intent_router.llm")
    def test_rewrite_fallback_on_error(self, mock_llm):
        """Falls back to raw query if rewrite LLM raises."""
        from services.orchestrator.nodes.intent_router import intent_router

        raw = "How does it work?"
        # First call (rewrite) fails, second (classify) succeeds
        mock_llm.invoke.side_effect = [RuntimeError("timeout"), MagicMock(content="chat")]

        state = _base_state(
            messages        = [HumanMessage(content=raw)],
            session_summary = "Goal: test | Decisions: none | Facts: none | Open: none",
        )
        result = intent_router(state)

        assert result["rewritten_query"] == raw
        assert result["intent"] == "chat"

    @patch("services.orchestrator.nodes.intent_router.llm")
    def test_invalid_intent_defaults_to_chat(self, mock_llm):
        """Unknown intent from LLM is coerced to 'chat'."""
        from services.orchestrator.nodes.intent_router import intent_router

        mock_llm.invoke.return_value = MagicMock(content="unknown_intent_xyz")
        state = _base_state(messages=[HumanMessage(content="random text")])
        result = intent_router(state)

        assert result["intent"] == "chat"
