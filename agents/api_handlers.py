from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, cast

import requests
from groq import Groq
from openai import OpenAI
from sarvamai import SarvamAI

try:
    from firecrawl import FirecrawlApp

    FIRECRAWL_AVAILABLE = True
except Exception:  # noqa: BLE001
    FIRECRAWL_AVAILABLE = False
    FirecrawlApp = None  # type: ignore[assignment]

try:
    from ddgs import DDGS

    DDGS_AVAILABLE = True
except Exception:  # noqa: BLE001
    DDGS_AVAILABLE = False

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
        self.firecrawl = (
            FirecrawlApp(
                api_key=settings.firecrawl_api_key,
                api_url=settings.firecrawl_cloud_url,
            )
            if (FIRECRAWL_AVAILABLE and settings.firecrawl_api_key)
            else None
        )
        self.groq = (
            Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        )
        self.sarvam = (
            SarvamAI(api_subscription_key=settings.sarvam_api_key)
            if settings.sarvam_api_key
            else None
        )

    def _message_payload(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        return [
            {"role": message.role, "content": message.content} for message in messages
        ]

    def _chat_via_groq(
        self, messages: List[ChatMessage], model: str, temperature: float
    ) -> str:
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
            raise ProviderError(
                f"Ollama call failed: {result.status_code} {result.text}"
            )
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
                if provider == "groq":
                    return self._chat_via_groq(
                        messages, model=model, temperature=temperature
                    )
                if provider == "ollama":
                    return self._chat_via_ollama(messages, model=model)
                raise ProviderError(f"Unsupported provider: {provider}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: {type(exc).__name__}: {exc}")

        raise ProviderError("All chat providers failed: " + " | ".join(errors))

    def _firecrawl_strategy(self) -> str:
        value = (settings.firecrawl_strategy or "self_hosted_first").strip().lower()
        if value not in {"self_hosted_first", "cloud_only", "self_hosted_only"}:
            return "self_hosted_first"
        return value

    def _is_cloud_base(self, base: str) -> bool:
        cloud_base = (
            settings.firecrawl_cloud_url.strip().rstrip("/")
            or "https://api.firecrawl.dev"
        )
        return base == cloud_base or "api.firecrawl.dev" in base

    def _selfhost_base_candidates(self) -> List[str]:
        bases: List[str] = []
        configured = settings.firecrawl_base_url.strip().rstrip("/")
        if configured and not self._is_cloud_base(configured):
            bases.append(configured)
        if "http://localhost:3002" not in bases:
            bases.append("http://localhost:3002")
        return bases

    def _firecrawl_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.firecrawl_api_key:
            headers["Authorization"] = f"Bearer {settings.firecrawl_api_key}"
        return headers

    def _selfhost_firecrawl_post(
        self, base: str, endpoint_candidates: List[str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        last_error = ""
        for endpoint in endpoint_candidates:
            try:
                response = requests.post(
                    base + endpoint,
                    headers=self._firecrawl_headers(),
                    json=payload,
                    timeout=120,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            if response.status_code < 400:
                return cast(Dict[str, Any], response.json())
            if response.status_code == 404:
                last_error = f"{response.status_code} {response.text}"
                continue
            raise ProviderError(
                f"Firecrawl self-host call failed: {response.status_code} {response.text}"
            )

        raise ProviderError(
            f"Firecrawl self-host endpoints not found. Last error: {last_error}"
        )

    def scrape_url(self, url: str) -> Dict[str, Any]:
        cloud_base = (
            settings.firecrawl_cloud_url.strip().rstrip("/")
            or "https://api.firecrawl.dev"
        )
        strategy = self._firecrawl_strategy()

        targets: List[tuple[str, str]] = []
        if strategy == "cloud_only":
            targets = [("cloud", cloud_base)]
        elif strategy == "self_hosted_only":
            targets = [
                ("self_hosted", base) for base in self._selfhost_base_candidates()
            ]
        else:
            targets = [
                *(("self_hosted", base) for base in self._selfhost_base_candidates()),
                ("cloud", cloud_base),
            ]

        errors: List[str] = []
        for mode, target_base in targets:
            try:
                if mode == "self_hosted":
                    return self._selfhost_firecrawl_post(
                        target_base,
                        ["/v2/scrape", "/v1/scrape", "/scrape"],
                        {"url": url, "formats": ["markdown"]},
                    )

                if not FIRECRAWL_AVAILABLE:
                    raise ProviderError(
                        "Firecrawl cloud call unavailable: install firecrawl-py."
                    )
                if not settings.firecrawl_api_key:
                    raise ProviderError(
                        "Firecrawl cloud call requires FIRECRAWL_API_KEY."
                    )
                cloud_client = FirecrawlApp(
                    api_key=settings.firecrawl_api_key, api_url=target_base
                )
                return cast(Any, cloud_client).scrape_url(url)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{mode}@{target_base}: {type(exc).__name__}: {exc}")

        raise ProviderError(
            "All Firecrawl scrape strategies failed: " + " | ".join(errors)
        )

    def crawl_url(
        self, url: str, limit: int = 1000, excludes: List[str] | None = None
    ) -> Dict[str, Any]:
        cloud_base = (
            settings.firecrawl_cloud_url.strip().rstrip("/")
            or "https://api.firecrawl.dev"
        )
        strategy = self._firecrawl_strategy()
        params = {
            "crawlerOptions": {
                "excludes": excludes or [],
                "includes": [],
                "limit": limit,
            }
        }

        targets: List[tuple[str, str]] = []
        if strategy == "cloud_only":
            targets = [("cloud", cloud_base)]
        elif strategy == "self_hosted_only":
            targets = [
                ("self_hosted", base) for base in self._selfhost_base_candidates()
            ]
        else:
            targets = [
                *(("self_hosted", base) for base in self._selfhost_base_candidates()),
                ("cloud", cloud_base),
            ]

        errors: List[str] = []
        for mode, target_base in targets:
            try:
                if mode == "self_hosted":
                    return self._selfhost_firecrawl_post(
                        target_base,
                        ["/v2/crawl", "/v1/crawl", "/crawl"],
                        {
                            "url": url,
                            "limit": limit,
                            "scrapeOptions": {"formats": ["markdown"]},
                        },
                    )

                if not FIRECRAWL_AVAILABLE:
                    raise ProviderError(
                        "Firecrawl cloud call unavailable: install firecrawl-py."
                    )
                if not settings.firecrawl_api_key:
                    raise ProviderError(
                        "Firecrawl cloud call requires FIRECRAWL_API_KEY."
                    )
                cloud_client = FirecrawlApp(
                    api_key=settings.firecrawl_api_key, api_url=target_base
                )
                return cast(Any, cloud_client).crawl_url(url, params=params)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{mode}@{target_base}: {type(exc).__name__}: {exc}")

        raise ProviderError(
            "All Firecrawl crawl strategies failed: " + " | ".join(errors)
        )

    def search_web(
        self, query: str, max_results: int | None = None
    ) -> List[Dict[str, str]]:
        if not DDGS_AVAILABLE:
            raise ProviderError("DuckDuckGo search unavailable: install ddgs package.")

        cap = max_results if max_results is not None else settings.ddg_max_results
        cap = max(1, min(int(cap), 10))

        with DDGS() as search_client:
            try:
                rows = list(
                    search_client.text(
                        query=query,
                        region=settings.ddg_region,
                        safesearch=settings.ddg_safesearch,
                        max_results=cap,
                    )
                )
            except TypeError:
                rows = list(
                    search_client.text(
                        keywords=query,
                        region=settings.ddg_region,
                        safesearch=settings.ddg_safesearch,
                        max_results=cap,
                    )
                )

        results: List[Dict[str, str]] = []
        for row in rows:
            url = str(row.get("href") or row.get("url") or "").strip()
            if not url:
                continue
            results.append(
                {
                    "title": str(row.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(row.get("body") or row.get("snippet") or "").strip(),
                    "source": "duckduckgo",
                }
            )
        return results

    def groq_chat(
        self,
        messages: List[ChatMessage],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        return self._run_chat_fallback(
            messages,
            [
                ("groq", model or settings.research_model_groq, "groq"),
                ("ollama", settings.ollama_fallback_model, "ollama"),
            ],
            temperature,
        )

    def ollama_chat(self, messages: List[ChatMessage], model: str | None = None) -> str:
        return self._run_chat_fallback(
            messages,
            [
                ("ollama", model or settings.ollama_fallback_model, "ollama"),
                ("groq", settings.groq_model_fast, "groq"),
            ],
            temperature=0.0,
        )

    def translate(
        self, text: str, target_language_code: str, source_language_code: str = "auto"
    ) -> Any:
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
