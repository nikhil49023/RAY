from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from unittest.mock import MagicMock

from services.orchestrator.nodes.memory_prefetch import memory_prefetch
from services.orchestrator.nodes.memory_writeback import memory_writeback


def test_memory_prefetch_uses_semantic_memory(monkeypatch):
    fake_result = {
        "behavioral_memories": ["Prefer tables for comparisons."],
        "memory_hits": [{"type": "conversation", "timestamp": "2026-04-05T00:00:00Z", "content": "Prior research on Groq."}],
        "memory_context": "[conversation | 2026-04-05T00:00:00Z]\nPrior research on Groq.",
    }
    monkeypatch.setattr(
        "services.orchestrator.nodes.memory_prefetch.retrieve_semantic_memory",
        lambda query, top_k=5: fake_result,
    )

    result = memory_prefetch({
        "messages": [HumanMessage(content="What did I research about Groq?")],
        "agent_mode": "research",
    })

    assert result["behavioral_memories"] == fake_result["behavioral_memories"]
    assert result["memory_hits"] == fake_result["memory_hits"]
    assert "Prior research on Groq" in result["memory_context"]


def test_memory_writeback_persists_turn_and_rules(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "services.orchestrator.nodes.memory_writeback.write_semantic_memory",
        lambda **kwargs: [{"type": "conversation", "content": kwargs["user_input"]}],
    )

    class FakeBehaviorIndex:
        def upsert(self, ids, vectors, payloads):
            captured.setdefault("payloads", []).extend(payloads)

    monkeypatch.setattr("services.orchestrator.nodes.memory_writeback.behavior_index", FakeBehaviorIndex())
    monkeypatch.setattr("services.orchestrator.nodes.memory_writeback.embedder.embed_query", lambda text: [0.1, 0.2])
    monkeypatch.setattr(
        "services.orchestrator.nodes.memory_writeback._resolve_llm",
        lambda: MagicMock(invoke=lambda messages: MagicMock(content="Prefer concise answers, Use tables for comparisons")),
    )

    result = memory_writeback({
        "messages": [
            HumanMessage(content="Keep it short."),
            AIMessage(content="I will keep it short."),
        ],
        "answer": "I will keep it short.",
    })

    assert result["memory_writes"] == [{"type": "conversation", "content": "Keep it short."}]
    assert result["behavioral_memories"] == ["Prefer concise answers", "Use tables for comparisons"]
    assert captured["payloads"][0]["rule"] == "Prefer concise answers"
