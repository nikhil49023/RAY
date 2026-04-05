from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from services.orchestrator.assistant_contract import build_assistant_contract


def _safe_provider_id(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip("-_")
    return cleaned or "groq"


def _normalize_model_id(model: str) -> str:
    value = (model or "").strip()
    return value or "openai/gpt-oss-20b"


def _provider_auth(base_url: str) -> tuple[str, str]:
    normalized = (base_url or "").strip().rstrip("/")
    if "localhost:4000" in normalized or "127.0.0.1:4000" in normalized:
        return "LiteLLM", "LITELLM_MASTER_KEY"
    return "Groq", "GROQ_API_KEY"


def _history_to_prompt(
    messages: List[dict],
    mode: str,
    visuals_enabled: bool,
    memory_context: str,
    behavioral_memories: List[str],
) -> str:
    mode_directives = {
        "standard": "Respond directly and use tools when they materially help.",
        "research": "Prefer grounded answers, cite concrete URLs when available, and be explicit about uncertainty.",
        "reasoning": "Focus on deliberate problem solving and only use external actions when needed.",
    }

    transcript: List[str] = []
    for item in messages:
        role = str(item.get("role", "user")).upper()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        transcript.append(f"[{role}]\n{content}")

    history_block = "\n\n".join(transcript).strip() or "[USER]\nHello"

    return (
        build_assistant_contract(
            visuals_enabled=visuals_enabled,
            memory_context=memory_context,
            behavioral_memories=behavioral_memories,
        )
        + "\n"
        + "You are the backend runtime for the RAY GUI chat application.\n"
        + "Operate as a capable local coding and research agent.\n"
        f"Mode: {mode}\n"
        f"{mode_directives.get(mode, mode_directives['standard'])}\n"
        "Return only the assistant response intended for the end user.\n\n"
        "Conversation transcript follows. Respond to the latest user request in context.\n\n"
        f"{history_block}\n"
    )


def _event_status(event_type: str) -> str | None:
    return {
        "thread.started": "Starting Codex session…",
        "turn.started": "Codex is working…",
        "item.completed": "Codex completed a tool or message step…",
        "turn.completed": "Codex finished the turn…",
    }.get(event_type)


def _event_log(payload: dict) -> dict | None:
    event_type = str(payload.get("type", "")).strip()
    if not event_type:
        return None

    detail = json.dumps(payload, ensure_ascii=False)
    if len(detail) > 900:
        detail = detail[:900] + "…"

    return {
        "node": "codex_cli",
        "title": event_type,
        "detail": detail,
        "provider": "Codex CLI",
    }


def _build_command(
    runtime: Dict[str, str],
    workdir: Path,
    prompt: str,
    model: str,
    output_file: Path,
) -> List[str]:
    provider_id = _safe_provider_id(runtime.get("codex_provider_id", "groq"))
    base_url = runtime.get("codex_base_url", "https://api.groq.com/openai/v1").rstrip("/")
    sandbox = runtime.get("codex_sandbox", "workspace-write")
    approval_policy = runtime.get("codex_approval_policy", "never")
    codex_path = runtime.get("codex_path", "codex")
    provider_name, env_key = _provider_auth(base_url)

    return [
        codex_path,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--cd",
        str(workdir),
        "-m",
        model,
        "-s",
        sandbox,
        "-o",
        str(output_file),
        "-c",
        f'model_providers.{provider_id}={{name="{provider_name}",base_url="{base_url}",env_key="{env_key}",wire_api="responses"}}',
        "-c",
        f'model_provider="{provider_id}"',
        "-c",
        f'approval_policy="{approval_policy}"',
        prompt,
    ]


def stream_codex_cli(
    *,
    messages: List[dict],
    runtime: Dict[str, str],
    mode: str,
    visuals_enabled: bool,
    memory_context: str,
    behavioral_memories: List[str],
    model: str | None,
    workdir: Path,
) -> Iterator[dict]:
    base_url = runtime.get("codex_base_url", "https://api.groq.com/openai/v1").rstrip("/")
    provider_name, auth_env = _provider_auth(base_url)
    auth_token = os.getenv(auth_env, "").strip()
    if not auth_token and auth_env == "LITELLM_MASTER_KEY":
        auth_token = "sk-litellm-master-key"

    if not auth_token:
        yield {
            "event": "error",
            "error": f"{auth_env} is not configured. Add it in Settings or environment before using the Codex runtime.",
        }
        return

    prompt = _history_to_prompt(
        messages,
        mode=mode,
        visuals_enabled=visuals_enabled,
        memory_context=memory_context,
        behavioral_memories=behavioral_memories,
    )
    resolved_model = _normalize_model_id(model or runtime.get("codex_model") or "openai/gpt-oss-20b")
    with tempfile.NamedTemporaryFile(prefix="ray_codex_last_", suffix=".txt", delete=False) as handle:
        output_file = Path(handle.name)

    env = os.environ.copy()
    env[auth_env] = auth_token

    command = _build_command(
        runtime=runtime,
        workdir=workdir,
        prompt=prompt,
        model=resolved_model,
        output_file=output_file,
    )

    yield {
        "event": "status",
        "status": f"Launching Codex CLI with {resolved_model} via {provider_name}…",
    }

    logs: List[dict] = []
    errors: List[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=str(workdir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        yield {
            "event": "error",
            "error": f'Codex CLI not found at `{runtime.get("codex_path", "codex")}`.',
        }
        output_file.unlink(missing_ok=True)
        return
    except Exception as exc:
        yield {
            "event": "error",
            "error": f"Failed to start Codex CLI: {exc}",
        }
        output_file.unlink(missing_ok=True)
        return

    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                errors.append(line)
                yield {
                    "event": "log",
                    "thinking_log": [{
                        "node": "codex_cli",
                        "title": "stdout",
                        "detail": line[:900],
                        "provider": "Codex CLI",
                    }],
                }
                continue

            event_type = str(payload.get("type", "")).strip()
            status = _event_status(event_type)
            if status:
                yield {"event": "status", "status": status}

            log_item = _event_log(payload)
            if log_item:
                logs.append(log_item)
                yield {"event": "log", "thinking_log": [log_item]}

            if event_type in {"error", "turn.failed"}:
                message = str(payload.get("message") or payload.get("error", {}).get("message") or "Codex execution failed.")
                errors.append(message)

        return_code = process.wait()
        answer = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
        if return_code != 0 and not answer:
            message = errors[-1] if errors else f"Codex CLI exited with status {return_code}."
            yield {"event": "error", "error": message}
            return

        if not answer:
            answer = "Codex finished without producing a final response."

        yield {
            "event": "done",
            "answer": answer,
            "thinking_log": logs[-40:],
            "evidence": [],
        }
    finally:
        output_file.unlink(missing_ok=True)
