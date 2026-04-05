"""
llm_factory.py — Unified LLM Provider Factory
----------------------------------------------
Routes to the correct provider based on a model_id string.
Supported prefixes: sarvam/, groq/, ollama/, openrouter/
Includes retry logic with exponential backoff for reliability.
"""

import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Optional, Any, Callable, TypeVar

from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger("ray.llm_factory")

# Load both env files — godmode-agent/.env first, then parent RAY/.env as fallback
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")
load_dotenv(_root.parent / ".env")  # parent RAY/.env as fallback

# Type variable for generic return types
T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Multiplier for exponential growth
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        logger.warning(
                            f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"LLM call failed after {max_retries + 1} attempts: {e}")
            raise last_exception

        return wrapper

    return decorator


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

    MODEL_INFO = {
        "groq/llama-3.3-70b-versatile": {
            "provider": "Groq",
            "specialty": "Balanced general assistant",
            "description": "Best default for everyday chat, research summaries, and polished long-form answers.",
            "features": ["Fast", "General chat", "Research-ready"],
        },
        "groq/llama-3.1-8b-instant": {
            "provider": "Groq",
            "specialty": "Speed-first replies",
            "description": "Good for quick back-and-forth conversations and lightweight drafting.",
            "features": ["Fastest", "Quick drafts", "Low latency"],
        },
        "groq/llama-4-scout-17b": {
            "provider": "Groq",
            "specialty": "Efficient reasoning",
            "description": "A lighter reasoning model suited for exploratory questions and structured planning.",
            "features": ["Reasoning", "Planning", "Responsive"],
        },
        "groq/deepseek-r1-distill-llama-70b": {
            "provider": "Groq",
            "specialty": "Deep reasoning",
            "description": "Best when the task needs step-heavy analysis, comparisons, or more deliberate thinking.",
            "features": ["Reasoning", "Analysis", "Math-heavy"],
        },
        "groq/mixtral-8x7b-32768": {
            "provider": "Groq",
            "specialty": "Long-context synthesis",
            "description": "Useful for summarizing larger prompts and synthesizing multiple ideas in one answer.",
            "features": ["Long context", "Summaries", "Synthesis"],
        },
        "openrouter/openrouter/free": {
            "provider": "OpenRouter",
            "specialty": "Flexible fallback",
            "description": "Routes through the free-tier path and is useful as a general backup model option.",
            "features": ["Fallback", "General chat", "Flexible"],
        },
        "openrouter/nvidia/nemotron-3-super-120b": {
            "provider": "OpenRouter",
            "specialty": "Research synthesis",
            "description": "Strong for dense technical responses, research-heavy prompts, and evidence synthesis.",
            "features": ["Research", "Technical depth", "Long answers"],
        },
        "openrouter/mistralai/devstral-2512": {
            "provider": "OpenRouter",
            "specialty": "Coding assistant",
            "description": "Best suited for code generation, implementation tasks, and debugging-oriented prompts.",
            "features": ["Coding", "Debugging", "Implementation"],
        },
        "sarvam/sarvam-m1": {
            "provider": "Sarvam",
            "specialty": "India-focused multilingual",
            "description": "Good for Indian-language and regional-context tasks while still handling general chat well.",
            "features": ["Multilingual", "India-first", "General chat"],
        },
        "ollama/deepseek-r1:8b": {
            "provider": "Ollama",
            "specialty": "Private local reasoning",
            "description": "Runs locally for private workflows and reasoning-heavy requests without a cloud dependency.",
            "features": ["Local", "Reasoning", "Private"],
        },
        "ollama/llama3": {
            "provider": "Ollama",
            "specialty": "Offline general chat",
            "description": "A local general-purpose model for simple conversations, drafts, and private usage.",
            "features": ["Local", "General chat", "Offline-friendly"],
        },
    }

    @classmethod
    def _is_model_available(cls, model_id: str) -> bool:
        prefix = model_id.split("/")[0]
        if prefix == "groq":
            return bool(os.getenv("GROQ_API_KEY"))
        if prefix == "sarvam":
            return bool(os.getenv("SARVAM_API_KEY"))
        if prefix == "openrouter":
            return bool(os.getenv("OPENROUTER_API_KEY"))
        if prefix == "ollama":
            return True
        return False

    @staticmethod
    @retry_with_backoff(max_retries=2, base_delay=0.5, retryable_exceptions=(ValueError, ImportError))
    def get_model(
        model_id: str = "groq/llama-3.3-70b-versatile",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Get an LLM instance for the specified model.

        Args:
            model_id: Model identifier with provider prefix (e.g., "groq/llama-3.3-70b-versatile")
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If required API key is not set
            ImportError: If required dependency is not installed
        """
        mid = model_id.lower()
        logger.info(f"Creating LLM instance for model: {model_id}")

        # ── Groq ──────────────────────────────────────────────────────────
        if mid.startswith("groq/"):
            try:
                from langchain_groq import ChatGroq
            except ImportError as exc:
                logger.error("Missing dependency: langchain-groq")
                raise ImportError(
                    "Missing optional dependency 'langchain-groq'. Install it in the active environment or switch to a non-Groq model."
                ) from exc
            key = os.getenv("GROQ_API_KEY", "")
            if not key:
                logger.error("GROQ_API_KEY not configured")
                raise ValueError("GROQ_API_KEY not set. Add it to .env or Settings.")
            logger.debug(f"Configuring Groq model: {model_id.split('/', 1)[1]}")
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
                logger.error("SARVAM_API_KEY not configured")
                raise ValueError("SARVAM_API_KEY not set. Add it to .env or Settings.")
            logger.debug(f"Configuring Sarvam model: {model_id.split('/', 1)[1]}")
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
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            logger.debug(f"Configuring Ollama model: {model_id.split('/', 1)[1]} at {base_url}")
            return ChatOllama(
                model=model_id.split("/", 1)[1],
                base_url=base_url,
                temperature=temperature,
            )

        # ── OpenRouter / fallback ─────────────────────────────────────────
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            logger.error("OPENROUTER_API_KEY not configured")
            raise ValueError("OPENROUTER_API_KEY not set. Add it to .env or Settings.")
        actual = model_id.replace("openrouter/", "")
        logger.debug(f"Configuring OpenRouter model: {actual}")
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
            if cls._is_model_available(mid):
                available[mid] = label
        return available if available else cls.MODELS

    @classmethod
    def list_model_entries(cls) -> list[dict]:
        model_ids = list(cls.list_models().keys())
        default_model = model_ids[0] if model_ids else None

        entries: list[dict] = []
        for model_id in model_ids:
            meta = cls.MODEL_INFO.get(model_id, {})
            entries.append({
                "id": model_id,
                "label": cls.MODELS.get(model_id, model_id),
                "provider": meta.get("provider", model_id.split("/", 1)[0].title()),
                "specialty": meta.get("specialty", "General assistant"),
                "description": meta.get("description", "General-purpose chat and task assistance."),
                "features": meta.get("features", ["Chat"]),
                "is_default": model_id == default_model,
            })
        return entries
