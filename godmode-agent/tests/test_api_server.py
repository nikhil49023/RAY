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
