"""
llm_factory.py — Unified LLM Provider Factory
----------------------------------------------
Routes to the correct provider based on a model_id string.
Supported prefixes: sarvam/, groq/, ollama/, openrouter/
"""

import os
from pathlib import Path
from typing import Optional, Any
from dotenv import load_dotenv

# Load both env files — godmode-agent/.env first, then parent RAY/.env as fallback
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
load_dotenv(_root.parent / ".env")  # parent RAY/.env as fallback


class LLMFactory:

    # ── Available Models Registry ─────────────────────────────────────────── #
    # Only models that work with your actual API keys
    MODELS = {
        # Groq (free, fast) — primary
        "groq/llama-3.3-70b-versatile":       "Llama 3.3 70B (Groq)",
        "groq/llama-3.1-8b-instant":          "Llama 3.1 8B Fast (Groq)",
        "groq/llama-4-scout-17b":             "Llama 4 Scout 17B (Groq)",
        "groq/deepseek-r1-distill-llama-70b": "DeepSeek R1 70B (Groq)",
        "groq/mixtral-8x7b-32768":            "Mixtral 8x7B (Groq)",
        # OpenRouter (free tier)
        "openrouter/openrouter/free":          "Auto Free (OpenRouter)",
        "openrouter/nvidia/nemotron-3-super-120b": "Nemotron 120B (OpenRouter)",
        "openrouter/mistralai/devstral-2512":  "Devstral (OpenRouter)",
        # Sarvam (Indian AI)
        "sarvam/sarvam-m1":                    "Sarvam M1 (Sarvam AI)",
        # Ollama (local)
        "ollama/deepseek-r1:8b":              "DeepSeek R1 8B (Local)",
        "ollama/llama3":                       "Llama 3 (Local)",
    }

    @staticmethod
    def get_model(
        model_id: str = "groq/llama-3.3-70b-versatile",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Any:
        mid = model_id.lower()

        # ── Groq ──────────────────────────────────────────────────────────
        if mid.startswith("groq/"):
            from langchain_groq import ChatGroq
            key = os.getenv("GROQ_API_KEY", "")
            if not key:
                raise ValueError("GROQ_API_KEY not set. Add it to .env or Settings.")
            return ChatGroq(
                api_key=key,
                model=model_id.split("/", 1)[1],
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # ── Sarvam (OpenAI-compatible) ────────────────────────────────────
        if mid.startswith("sarvam/"):
            from langchain_openai import ChatOpenAI
            key = os.getenv("SARVAM_API_KEY", "")
            if not key:
                raise ValueError("SARVAM_API_KEY not set. Add it to .env or Settings.")
            return ChatOpenAI(
                api_key=key,
                model=model_id.split("/", 1)[1],
                base_url="https://api.sarvam.ai/v1",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # ── Ollama (local) ────────────────────────────────────────────────
        if mid.startswith("ollama/"):
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=model_id.split("/", 1)[1],
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=temperature,
            )

        # ── OpenRouter / fallback ─────────────────────────────────────────
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set. Add it to .env or Settings.")
        actual = model_id.replace("openrouter/", "")
        return ChatOpenAI(
            api_key=key,
            model=actual,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @classmethod
    def list_models(cls) -> dict:
        """Return available models, filtering out those without API keys."""
        available = {}
        for mid, label in cls.MODELS.items():
            prefix = mid.split("/")[0]
            if prefix == "groq" and os.getenv("GROQ_API_KEY"):
                available[mid] = label
            elif prefix == "sarvam" and os.getenv("SARVAM_API_KEY"):
                available[mid] = label
            elif prefix == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
                available[mid] = label
            elif prefix == "ollama":
                available[mid] = label  # always available if ollama running
        return available if available else cls.MODELS
