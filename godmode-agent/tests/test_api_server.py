from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api import server


def test_chat_uses_configured_codex_model(monkeypatch):
    settings = {
        "agentRuntime": {
            "backend": "codex_cli",
            "codexModel": "openai/gpt-oss-20b",
        },
        "ui": {
            "renderVisualsInline": False,
        },
    }
    runtime = {
        "backend": "codex_cli",
        "codex_model": "openai/gpt-oss-20b",
    }
    captured: dict[str, str] = {}

    monkeypatch.setattr(server, "load_user_settings", lambda: settings)
    monkeypatch.setattr(server, "apply_runtime_settings", lambda current: current)
    monkeypatch.setattr(server, "get_agent_runtime_config", lambda current: runtime)

    def fake_stream_codex_cli(**kwargs):
        captured["model"] = kwargs["model"]
        yield {
            "event": "done",
            "answer": "hello from codex",
            "thinking_log": [],
            "evidence": [],
        }

    monkeypatch.setattr(server, "stream_codex_cli", fake_stream_codex_cli)

    client = TestClient(server.app)
    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "model": "groq/llama-3.3-70b-versatile",
        },
    )

    assert response.status_code == 200
    assert captured["model"] == "openai/gpt-oss-20b"
    assert '0:"hello from codex"' in response.text


def test_codex_proxy_models_match_runtime_ids():
    client = TestClient(server.app)
    response = client.get("/api/codex-openai/v1/models")

    assert response.status_code == 200
    payload = response.json()

    assert payload["data"][0]["id"] == "openai/gpt-oss-20b"
    assert payload["data"][1]["id"] == "openai/gpt-oss-120b"


def test_thread_delete_removes_saved_thread_and_session_memory(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(server, "THREADS_DIR", tmp_path)

    def fake_write_semantic_memory(**kwargs):
        captured["saved_session_id"] = kwargs["session_id"]
        return []

    class FakeExecutionIndex:
        def delete_by_field(self, field, value):
            captured["deleted_field"] = field
            captured["deleted_value"] = value

    monkeypatch.setattr(server, "write_semantic_memory", fake_write_semantic_memory)
    monkeypatch.setattr(server, "execution_index", FakeExecutionIndex())

    client = TestClient(server.app)
    save_response = client.post(
        "/api/threads",
        json={
            "id": "chat_123",
            "title": "Chat",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["id"] == "chat_123"
    assert (tmp_path / "chat_123.json").exists()
    assert captured["saved_session_id"] == "chat_123"

    delete_response = client.delete("/api/threads/chat_123")

    assert delete_response.status_code == 200
    assert not (tmp_path / "chat_123.json").exists()
    assert captured["deleted_field"] == "session_id"
    assert captured["deleted_value"] == "chat_123"
