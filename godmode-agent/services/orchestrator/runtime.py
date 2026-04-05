"""
runtime.py — Runtime settings and provider configuration
--------------------------------------------------------
Loads persisted user settings, applies them to the process environment,
and exposes normalized runtime configuration for orchestration nodes.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SETTINGS_FILE = DATA_DIR / "user_settings.json"

DEFAULT_FIRECRAWL_BASE_URL = "http://localhost:3002"
DEFAULT_FIRECRAWL_CLOUD_URL = "https://api.firecrawl.dev"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_settings() -> Dict[str, Any]:
    return {
        "temperature": 0.1,
        "apiKeys": {
            "groq": os.getenv("GROQ_API_KEY", ""),
            "sarvam": os.getenv("SARVAM_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        },
        "firecrawl": {
            "strategy": "self_hosted_first",
            "baseUrl": os.getenv("FIRECRAWL_BASE_URL", DEFAULT_FIRECRAWL_BASE_URL),
            "cloudUrl": os.getenv("FIRECRAWL_CLOUD_URL", DEFAULT_FIRECRAWL_CLOUD_URL),
            "fallbackApiKey": os.getenv("FIRECRAWL_API_KEY", ""),
        },
        "ui": {
            "showThinkingLogs": True,
            "renderVisualsInline": False,
            "researchOutput": "document",
        },
        "search": {
            "provider": "duckduckgo",
            "reranker": "ReLU",
        },
        "agentRuntime": {
            "backend": os.getenv("RAY_AGENT_BACKEND", "langgraph"),
            "codexPath": os.getenv("CODEX_CLI_PATH", "codex"),
            "codexModel": os.getenv("CODEX_MODEL", "openai/gpt-oss-20b"),
            "codexProviderId": os.getenv("CODEX_PROVIDER_ID", "groq"),
            "codexBaseUrl": os.getenv("CODEX_BASE_URL", "https://api.groq.com/openai/v1"),
            "codexSandbox": os.getenv("CODEX_SANDBOX", "workspace-write"),
            "codexApprovalPolicy": os.getenv("CODEX_APPROVAL_POLICY", "never"),
        },
    }


def load_user_settings() -> Dict[str, Any]:
    settings = default_settings()
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                settings = _deep_merge(settings, stored)
        except Exception:
            pass
    return settings


def save_user_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    settings = _deep_merge(default_settings(), data if isinstance(data, dict) else {})
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    return settings


def apply_runtime_settings(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or load_user_settings()

    api_keys = settings.get("apiKeys", {})
    if api_keys.get("groq"):
        os.environ["GROQ_API_KEY"] = str(api_keys["groq"])
    if api_keys.get("sarvam"):
        os.environ["SARVAM_API_KEY"] = str(api_keys["sarvam"])
    if api_keys.get("openrouter"):
        os.environ["OPENROUTER_API_KEY"] = str(api_keys["openrouter"])

    firecrawl = settings.get("firecrawl", {})
    base_url = str(firecrawl.get("baseUrl") or DEFAULT_FIRECRAWL_BASE_URL).rstrip("/")
    cloud_url = str(firecrawl.get("cloudUrl") or DEFAULT_FIRECRAWL_CLOUD_URL).rstrip("/")
    fallback_key = str(firecrawl.get("fallbackApiKey") or "").strip()

    if base_url:
        os.environ["FIRECRAWL_BASE_URL"] = base_url
        os.environ["FIRECRAWL_API_URL"] = base_url
    if cloud_url:
        os.environ["FIRECRAWL_CLOUD_URL"] = cloud_url
    if fallback_key:
        os.environ["FIRECRAWL_API_KEY"] = fallback_key

    os.environ["RAY_SEARCH_PROVIDER"] = str(settings.get("search", {}).get("provider", "duckduckgo"))
    os.environ["RAY_RERANKER"] = str(settings.get("search", {}).get("reranker", "ReLU"))
    os.environ["RAY_RESEARCH_OUTPUT"] = str(settings.get("ui", {}).get("researchOutput", "document"))
    os.environ["RAY_SHOW_THINKING_LOGS"] = "1" if settings.get("ui", {}).get("showThinkingLogs", True) else "0"
    runtime = settings.get("agentRuntime", {})
    os.environ["RAY_AGENT_BACKEND"] = str(runtime.get("backend", "langgraph"))
    os.environ["CODEX_CLI_PATH"] = str(runtime.get("codexPath", "codex"))
    os.environ["CODEX_MODEL"] = str(runtime.get("codexModel", "openai/gpt-oss-20b"))
    os.environ["CODEX_PROVIDER_ID"] = str(runtime.get("codexProviderId", "groq"))
    os.environ["CODEX_BASE_URL"] = str(runtime.get("codexBaseUrl", "https://api.groq.com/openai/v1")).rstrip("/")
    os.environ["CODEX_SANDBOX"] = str(runtime.get("codexSandbox", "workspace-write"))
    os.environ["CODEX_APPROVAL_POLICY"] = str(runtime.get("codexApprovalPolicy", "never"))

    return settings


def get_firecrawl_config(settings: Dict[str, Any] | None = None) -> Dict[str, str]:
    settings = settings or load_user_settings()
    firecrawl = settings.get("firecrawl", {})
    base_url = str(firecrawl.get("baseUrl") or DEFAULT_FIRECRAWL_BASE_URL).rstrip("/")
    cloud_url = str(firecrawl.get("cloudUrl") or DEFAULT_FIRECRAWL_CLOUD_URL).rstrip("/")
    fallback_key = str(firecrawl.get("fallbackApiKey") or "").strip()
    strategy = str(firecrawl.get("strategy") or "self_hosted_first").strip() or "self_hosted_first"
    return {
        "strategy": strategy,
        "base_url": base_url,
        "cloud_url": cloud_url,
        "fallback_api_key": fallback_key,
    }


def get_agent_runtime_config(settings: Dict[str, Any] | None = None) -> Dict[str, str]:
    settings = settings or load_user_settings()
    runtime = settings.get("agentRuntime", {})
    return {
        "backend": str(runtime.get("backend") or "langgraph").strip() or "langgraph",
        "codex_path": str(runtime.get("codexPath") or "codex").strip() or "codex",
        "codex_model": str(runtime.get("codexModel") or "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b",
        "codex_provider_id": str(runtime.get("codexProviderId") or "groq").strip() or "groq",
        "codex_base_url": str(runtime.get("codexBaseUrl") or "https://api.groq.com/openai/v1").strip().rstrip("/") or "https://api.groq.com/openai/v1",
        "codex_sandbox": str(runtime.get("codexSandbox") or "workspace-write").strip() or "workspace-write",
        "codex_approval_policy": str(runtime.get("codexApprovalPolicy") or "never").strip() or "never",
    }
