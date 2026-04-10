import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    firecrawl_base_url: str = os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")
    firecrawl_strategy: str = os.getenv("FIRECRAWL_STRATEGY", "self_hosted_first")
    firecrawl_cloud_url: str = os.getenv(
        "FIRECRAWL_CLOUD_URL", "https://api.firecrawl.dev"
    )
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "")
    huggingface_api_token: str = os.getenv("HUGGINGFACE_API_TOKEN", "")

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # LiteLLM router settings for agentic orchestration
    litellm_base_url: str = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key: str = os.getenv("LITELLM_API_KEY", "sk-litellm-master-key")
    litellm_model: str = os.getenv("LITELLM_MODEL", "premium-thinker")

    research_model_groq: str = os.getenv(
        "RESEARCH_MODEL_GROQ", "llama-3.3-70b-versatile"
    )
    translation_model_sarvam: str = os.getenv(
        "TRANSLATION_MODEL_SARVAM", "sarvam-translate"
    )
    ollama_fallback_model: str = os.getenv("OLLAMA_FALLBACK_MODEL", "deepseek-r1:8b")

    # Dynamic semantic router controls
    router_default_mode: str = os.getenv("ROUTER_DEFAULT_MODE", "semantic")
    enable_ensemble: bool = _as_bool(os.getenv("ENABLE_ENSEMBLE", "true"), default=True)
    ensemble_threshold: int = int(os.getenv("ENSEMBLE_THRESHOLD", "18"))

    # Groq free-tier options
    groq_model_strong: str = os.getenv("GROQ_MODEL_STRONG", "openai/gpt-oss-120b")
    groq_model_quality: str = os.getenv("GROQ_MODEL_QUALITY", "llama-3.3-70b-versatile")
    groq_model_fast: str = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")
    groq_model_long_context: str = os.getenv(
        "GROQ_MODEL_LONG_CONTEXT", "llama-4-scout-17b"
    )


    # Sarvam options
    sarvam_model_flagship: str = os.getenv("SARVAM_MODEL_FLAGSHIP", "sarvam-105b")
    sarvam_model_realtime: str = os.getenv("SARVAM_MODEL_REALTIME", "sarvam-30b")

    # Artifacts / skills
    artifacts_dir: str = os.getenv("ARTIFACTS_DIR", "data/artifacts")
    huggingface_image_model: str = os.getenv(
        "HUGGINGFACE_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"
    )
    ddg_region: str = os.getenv("DDG_REGION", "wt-wt")
    ddg_safesearch: str = os.getenv("DDG_SAFESEARCH", "moderate")
    ddg_max_results: int = int(os.getenv("DDG_MAX_RESULTS", "5"))

    # Agentic local RAG controls
    rag_chroma_host: str = os.getenv("RAG_CHROMA_HOST", "localhost")
    rag_chroma_port: int = int(os.getenv("RAG_CHROMA_PORT", "8000"))
    rag_chroma_local_path: str = os.getenv("RAG_CHROMA_LOCAL_PATH", "data/chroma")
    rag_collection_name: str = os.getenv("RAG_COLLECTION_NAME", "ray_docs")
    rag_embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "nomic-embed-text")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))

    # Agentic orchestrator controls
    agentic_enable_crewai: bool = _as_bool(
        os.getenv("AGENTIC_ENABLE_CREWAI", "true"), default=True
    )
    agentic_default_chart: str = os.getenv("AGENTIC_DEFAULT_CHART", "bar")
    agentic_system_prompt: str = os.getenv(
        "AGENTIC_SYSTEM_PROMPT",
        (
            "You are RAY, an autonomous assistant for local-first research workflows. "
            "Prefer local Chroma RAG evidence first, then web scraping for missing context. "
            "Never fabricate facts, distinguish facts from assumptions, and clearly state when data is unavailable."
        ),
    )

    # Behavioral memory (RAG-backed preference reinforcement)
    behavior_memory_enabled: bool = _as_bool(
        os.getenv("BEHAVIOR_MEMORY_ENABLED", "true"), default=True
    )
    behavior_memory_collection: str = os.getenv(
        "BEHAVIOR_MEMORY_COLLECTION", "ray_behavior"
    )
    behavior_memory_top_k: int = int(os.getenv("BEHAVIOR_MEMORY_TOP_K", "4"))

    # Hardware profile (for UI/runtime guidance)
    hardware_vram_budget_gb: int = int(os.getenv("HARDWARE_VRAM_BUDGET_GB", "4"))
    hardware_quantization_profile: str = os.getenv(
        "HARDWARE_QUANTIZATION_PROFILE",
        "GGUF + KV Cache Quantization",
    )


settings = Settings()
