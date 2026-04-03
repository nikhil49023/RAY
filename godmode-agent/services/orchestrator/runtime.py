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
            "renderVisualsInline": True,
            "researchOutput": "document",
        },
        "search": {
            "provider": "duckduckgo",
            "reranker": "ReLU",
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
