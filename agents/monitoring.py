from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List

import requests

from agents.config import settings

USAGE_LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "usage" / "usage_log.jsonl"


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except TypeError:
            pass
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return str(value)


def log_usage(provider: str, model: str, usage: Dict[str, Any] | None = None) -> None:
    USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "usage": usage or {},
    }
    with USAGE_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True, default=_json_default) + "\n")


def read_usage(limit: int = 2000) -> List[Dict[str, Any]]:
    if not USAGE_LOG_PATH.exists():
        return []
    lines = USAGE_LOG_PATH.read_text(encoding="utf-8").splitlines()
    if limit > 0:
        lines = lines[-limit:]
    records: List[Dict[str, Any]] = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def summarize_usage(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"total_calls": len(records), "providers": {}, "models": {}}
    for rec in records:
        provider = rec.get("provider", "unknown")
        model = rec.get("model", "unknown")
        usage = rec.get("usage") or {}

        summary["providers"].setdefault(provider, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        summary["models"].setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

        summary["providers"][provider]["calls"] += 1
        summary["providers"][provider]["input_tokens"] += input_tokens
        summary["providers"][provider]["output_tokens"] += output_tokens
        summary["providers"][provider]["total_tokens"] += total_tokens

        summary["models"][model]["calls"] += 1
        summary["models"][model]["input_tokens"] += input_tokens
        summary["models"][model]["output_tokens"] += output_tokens
        summary["models"][model]["total_tokens"] += total_tokens

    return summary


def query_openrouter_credit() -> Dict[str, Any]:
    if not settings.openrouter_api_key:
        return {"provider": "openrouter", "status": "missing_api_key"}

    try:
        response = requests.get(
            settings.openrouter_base_url.rstrip("/") + "/auth/key",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=20,
        )
        if response.status_code >= 400:
            return {"provider": "openrouter", "status": "error", "detail": response.text[:500]}

        payload = response.json()
        data = payload.get("data", payload)
        return {
            "provider": "openrouter",
            "status": "ok",
            "limit": data.get("limit"),
            "usage": data.get("usage"),
            "limit_remaining": data.get("limit_remaining") or data.get("credits_remaining"),
            "raw": data,
        }
    except Exception as exc:  # noqa: BLE001
        return {"provider": "openrouter", "status": "error", "detail": str(exc)}


def query_groq_credit() -> Dict[str, Any]:
    # Groq currently does not expose a stable public credits endpoint in OpenAI-compatible APIs.
    if not settings.groq_api_key:
        return {"provider": "groq", "status": "missing_api_key"}

    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            timeout=20,
        )
        if response.status_code >= 400:
            return {"provider": "groq", "status": "error", "detail": response.text[:500]}
        return {
            "provider": "groq",
            "status": "ok",
            "note": "Model access verified. Remaining credits are not exposed by this endpoint.",
            "model_count": len(response.json().get("data", [])),
        }
    except Exception as exc:  # noqa: BLE001
        return {"provider": "groq", "status": "error", "detail": str(exc)}


def query_sarvam_credit() -> Dict[str, Any]:
    # Sarvam public balance endpoints may vary by account/product.
    if not settings.sarvam_api_key:
        return {"provider": "sarvam", "status": "missing_api_key"}
    return {
        "provider": "sarvam",
        "status": "unknown",
        "note": "No stable public credit endpoint wired yet. Usage is tracked locally from requests.",
    }
