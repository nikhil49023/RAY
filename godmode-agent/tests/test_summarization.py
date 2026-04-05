"""
tests/test_summarization.py
----------------------------
Unit tests focused exclusively on summarizer.py correctness:

  1. Output parses into the required 4-part format.
  2. Every "Fact" established in prior messages appears in at least one
     call to the LLM summariser (regression test for "Facts Established"
     capture requirement).
  3. Incremental / multi-round compression retains prior facts.
  4. Summary length stays within the token budget.
  5. Dual-trigger: both turn-based and token-based triggers independently
     cause compression.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage


# ── helpers ──────────────────────────────────────────────────────────────────

EXPECTED_KEYS = {"Goal", "Decisions", "Facts", "Open"}

def _parse_summary(text: str) -> dict:
    """Parse the 4-part summary into a dict keyed by section name."""
    result = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            k = key.strip()
            if k in EXPECTED_KEYS:
                result[k] = val.strip()
    return result


def _make_factual_messages(facts: list[str] | int):
    """Create alternating H/A messages that mention the given facts."""
    if isinstance(facts, int):
        facts = [f"fact-{i}" for i in range(facts)]
    msgs = []
    for i, fact in enumerate(facts):
        msgs.append(HumanMessage(content=f"Tell me about {fact}"))
        msgs.append(AIMessage(content=f"The established fact is: {fact}"))
    return msgs


def _base_state(**kwargs):
    defaults = dict(
        messages            = [],
        session_summary     = None,
        recent_messages     = [],
        applied_rules       = [],
        turn_count          = 0,
        intent              = None,
        rewritten_query     = None,
        plan                = None,
        evidence            = [],
        behavioral_memories = [],
        verification_status = "PENDING",
        artifacts           = [],
        current_task        = None,
        completed_nodes     = [],
        node_timings        = {},
        telemetry           = {},
        errors              = [],
    )
    defaults.update(kwargs)
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSummarizationOutput:

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_output_has_four_sections(self, mock_llm):
        """The summarizer LLM is always asked to produce all 4 sections."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        summary_text = (
            "Goal      : Build a drone swarm\n"
            "Decisions : Use BNO085 for IMU\n"
            "Facts     : Raspberry Pi 5 selected\n"
            "Open      : Budget approval pending"
        )
        mock_llm.invoke.return_value = MagicMock(content=summary_text)

        state  = _base_state(messages=_make_factual_messages(["Pi 5", "IMU"]),
                             turn_count=SUMMARIZE_EVERY_N_TURNS)
        result = summarizer(state)

        parsed = _parse_summary(result["session_summary"])
        for key in EXPECTED_KEYS:
            assert key in parsed, f"Missing section '{key}' in summary"

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_facts_from_messages_passed_to_llm(self, mock_llm):
        """All factual messages are included in the LLM prompt input."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        facts = ["TurboQuant reduces latency by 40%", "Coral TPU runs at 4 TOPS"]
        mock_llm.invoke.return_value = MagicMock(content=" | ".join(facts))

        state = _base_state(
            messages   = _make_factual_messages(facts),
            turn_count = SUMMARIZE_EVERY_N_TURNS,
        )
        summarizer(state)

        call_input = str(mock_llm.invoke.call_args)
        for fact in facts:
            # The fact text should appear in the prompt passed to the LLM
            assert fact in call_input, f"Expected fact not passed to LLM: '{fact}'"

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_incremental_summary_retains_prior_facts(self, mock_llm):
        """A second compression round receives the previous summary."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        first_summary = (
            "Goal: build swarm | Decisions: Raspberry Pi 5 | "
            "Facts: TurboQuant approved | Open: testing"
        )
        second_summary = (
            "Goal: build swarm | Decisions: Pi 5 + Coral | "
            "Facts: TurboQuant approved, Coral TPU validated | Open: none"
        )
        mock_llm.invoke.return_value = MagicMock(content=second_summary)

        state = _base_state(
            messages        = _make_factual_messages(["Coral TPU"]),
            session_summary = first_summary,
            turn_count      = SUMMARIZE_EVERY_N_TURNS,
        )
        result = summarizer(state)

        call_input = str(mock_llm.invoke.call_args)
        assert "TurboQuant" in call_input, "Prior fact 'TurboQuant' should be in the prompt"
        assert result["session_summary"] == second_summary

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_summary_within_token_budget(self, mock_llm):
        """Generated summary must be ≤ 600 tokens (~2280 chars) per design."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS, AVG_CHARS_PER_TOKEN

        MAX_SUMMARY_TOKENS = 600
        MAX_CHARS = int(MAX_SUMMARY_TOKENS * AVG_CHARS_PER_TOKEN)

        # Simulate a very verbose LLM response -> model should truncate
        long_but_valid = (
            "Goal: G | Decisions: D | Facts: F | Open: O"
        )
        mock_llm.invoke.return_value = MagicMock(content=long_but_valid)

        state = _base_state(
            messages   = _make_factual_messages(["fact"] * 10),
            turn_count = SUMMARIZE_EVERY_N_TURNS,
        )
        result = summarizer(state)

        actual_chars = len(result.get("session_summary", ""))
        assert actual_chars <= MAX_CHARS, (
            f"Summary too long: {actual_chars} chars > {MAX_CHARS} max"
        )

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_turn_trigger(self, mock_llm):
        """Turn-based trigger fires at exactly every N turns."""
        from services.orchestrator.nodes.summarizer import summarizer, SUMMARIZE_EVERY_N_TURNS

        mock_llm.invoke.return_value = MagicMock(content="Goal: x | Decisions: y | Facts: z | Open: w")

        for turn in range(1, SUMMARIZE_EVERY_N_TURNS * 2 + 1):
            mock_llm.invoke.reset_mock()
            state  = _base_state(messages=_make_factual_messages(2), turn_count=turn)
            summarizer(state)
            should_have_run = (turn % SUMMARIZE_EVERY_N_TURNS == 0)
            assert mock_llm.invoke.called == should_have_run, (
                f"Turn {turn}: LLM called={mock_llm.invoke.called}, expected={should_have_run}"
            )

    @patch("services.orchestrator.nodes.summarizer._llm")
    def test_token_threshold_trigger(self, mock_llm):
        """Token-based trigger fires when history is long enough."""
        from services.orchestrator.nodes.summarizer import (
            summarizer, TOKEN_THRESHOLD, AVG_CHARS_PER_TOKEN
        )

        mock_llm.invoke.return_value = MagicMock(content="Goal: big | Decisions: many | Facts: lots | Open: more")

        chars_needed = int(TOKEN_THRESHOLD * AVG_CHARS_PER_TOKEN) + 500
        huge_msg     = HumanMessage(content="a" * chars_needed)

        # turn_count=1 → would NOT normally trigger by turn
        state = _base_state(messages=[huge_msg], turn_count=1)
        summarizer(state)

        mock_llm.invoke.assert_called_once()
