from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, cast

import requests
from firecrawl import FirecrawlApp
from groq import Groq
from openai import OpenAI
from sarvamai import SarvamAI

from agents.config import settings
from agents.monitoring import log_usage


class ProviderError(RuntimeError):
    """Raised when a provider call fails and no fallback is available."""


@dataclass
class ChatMessage:
    role: str
    content: str


class MultiProviderClients:
    def __init__(self) -> None:
        self.firecrawl = FirecrawlApp(api_key=settings.firecrawl_api_key) if settings.firecrawl_api_key else None
        self.groq = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        self.openrouter = (
            OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
            if settings.openrouter_api_key
            else None
        )
        self.sarvam = SarvamAI(api_subscription_key=settings.sarvam_api_key) if settings.sarvam_api_key else None

    def _message_payload(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    def _chat_via_groq(self, messages: List[ChatMessage], model: str, temperature: float) -> str:
        if not self.groq:
            raise ProviderError("Groq is not configured. Set GROQ_API_KEY.")

        response = self.groq.chat.completions.create(
            model=model,
            temperature=temperature,
            top_p=1,
            messages=cast(Any, self._message_payload(messages)),
        )
        log_usage("groq", model, cast(Any, getattr(response, "usage", None)))
        return response.choices[0].message.content or ""

    def _chat_via_openrouter(self, messages: List[ChatMessage], model: str, temperature: float) -> str:
        if not self.openrouter:
            raise ProviderError("OpenRouter is not configured. Set OPENROUTER_API_KEY.")

        response = self.openrouter.chat.completions.create(
            model=model,
            temperature=temperature,
            top_p=1,
            messages=cast(Any, self._message_payload(messages)),
        )
        log_usage("openrouter", model, cast(Any, getattr(response, "usage", None)))
        return response.choices[0].message.content or ""

    def _chat_via_ollama(self, messages: List[ChatMessage], model: str) -> str:
        payload = {
            "model": model,
            "messages": self._message_payload(messages),
            "stream": False,
            "options": {"temperature": 0},
        }
        endpoint = settings.ollama_base_url.rstrip("/") + "/api/chat"
        result = requests.post(endpoint, json=payload, timeout=120)
        if result.status_code >= 400:
            raise ProviderError(f"Ollama call failed: {result.status_code} {result.text}")
        body = result.json()
        log_usage("ollama", model, body.get("usage", {}))
        return body.get("message", {}).get("content", "")

    def _run_chat_fallback(
        self,
        messages: List[ChatMessage],
        candidates: List[tuple[str, str, str]],
        temperature: float,
    ) -> str:
        errors: List[str] = []
        for provider, model, label in candidates:
            try:
                if provider == "openrouter":
                    return self._chat_via_openrouter(messages, model=model, temperature=temperature)
                if provider == "groq":
                    return self._chat_via_groq(messages, model=model, temperature=temperature)
                if provider == "ollama":
                    return self._chat_via_ollama(messages, model=model)
                raise ProviderError(f"Unsupported provider: {provider}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: {type(exc).__name__}: {exc}")

        raise ProviderError("All chat providers failed: " + " | ".join(errors))

    def _firecrawl_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.firecrawl_api_key:
            headers["Authorization"] = f"Bearer {settings.firecrawl_api_key}"
        return headers

    def _selfhost_firecrawl_post(self, base: str, endpoint_candidates: List[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        last_error = ""
        for endpoint in endpoint_candidates:
            response = requests.post(
                base + endpoint,
                headers=self._firecrawl_headers(),
                json=payload,
                timeout=120,
            )
            if response.status_code < 400:
                return cast(Dict[str, Any], response.json())
            if response.status_code == 404:
                last_error = f"{response.status_code} {response.text}"
                continue
            raise ProviderError(f"Firecrawl self-host call failed: {response.status_code} {response.text}")

        raise ProviderError(f"Firecrawl self-host endpoints not found. Last error: {last_error}")

    def scrape_url(self, url: str) -> Dict[str, Any]:
        base = settings.firecrawl_base_url.rstrip("/")
        if base != "https://api.firecrawl.dev":
            return self._selfhost_firecrawl_post(
                base,
                ["/v2/scrape", "/v1/scrape", "/scrape"],
                {"url": url},
            )

        if not self.firecrawl:
            raise ProviderError("Firecrawl is not configured. Set FIRECRAWL_API_KEY.")
        return cast(Any, self.firecrawl).scrape_url(url)

    def crawl_url(self, url: str, limit: int = 1000, excludes: List[str] | None = None) -> Dict[str, Any]:
        base = settings.firecrawl_base_url.rstrip("/")
        params = {
            "crawlerOptions": {
                "excludes": excludes or [],
                "includes": [],
                "limit": limit,
            }
        }

        if base != "https://api.firecrawl.dev":
            return self._selfhost_firecrawl_post(
                base,
                ["/v2/crawl", "/v1/crawl", "/crawl"],
                {"url": url, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
            )

        if not self.firecrawl:
            raise ProviderError("Firecrawl is not configured. Set FIRECRAWL_API_KEY.")
        return cast(Any, self.firecrawl).crawl_url(url, params=params)

    def groq_chat(self, messages: List[ChatMessage], model: str | None = None, temperature: float = 0.0) -> str:
        return self._run_chat_fallback(
            messages,
            [
                ("groq", model or settings.research_model_groq, "groq"),
                ("openrouter", settings.openrouter_model_auto_free, "openrouter"),
                ("ollama", settings.ollama_fallback_model, "ollama"),
            ],
            temperature,
        )

    def openrouter_chat(self, messages: List[ChatMessage], model: str | None = None, temperature: float = 0.0) -> str:
        return self._run_chat_fallback(
            messages,
            [
                ("groq", settings.groq_model_fast, "groq"),
                ("openrouter", model or settings.analysis_model_openrouter, "openrouter"),
                ("ollama", settings.ollama_fallback_model, "ollama"),
            ],
            temperature,
        )

    def ollama_chat(self, messages: List[ChatMessage], model: str | None = None) -> str:
        return self._run_chat_fallback(
            messages,
            [
                ("ollama", model or settings.ollama_fallback_model, "ollama"),
                ("openrouter", settings.openrouter_model_auto_free, "openrouter"),
                ("groq", settings.groq_model_fast, "groq"),
            ],
            temperature=0.0,
        )

    def translate(self, text: str, target_language_code: str, source_language_code: str = "auto") -> Any:
        if not self.sarvam:
            raise ProviderError("Sarvam is not configured. Set SARVAM_API_KEY.")
        response = self.sarvam.text.translate(
            input=text,
            source_language_code=source_language_code,
            target_language_code=target_language_code,
            speaker_gender="Male",
        )
        log_usage("sarvam", settings.translation_model_sarvam, None)
        return response
