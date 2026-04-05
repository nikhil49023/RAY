from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
from typing import Any, Dict, List

import fire
import requests

from agents.api_handlers import MultiProviderClients
from agents.config import settings
from agents.orchestrator import PersonalAgent


class AgenticOrchestrator:
    """CrewAI-style autonomous orchestrator with safe fallbacks."""

    def __init__(self) -> None:
        self.clients = MultiProviderClients()
        self.personal = PersonalAgent()
        self.root_dir = Path(__file__).resolve().parents[1]
        self.artifacts_dir = Path(settings.artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        rag_local_path = Path(settings.rag_chroma_local_path)
        self.rag_local_path = (
            rag_local_path
            if rag_local_path.is_absolute()
            else self.root_dir / rag_local_path
        )

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "artifact"

    def _save_html_artifact(self, objective: str, html: str) -> str:
        name = self._slugify(objective)[:64]
        path = self.artifacts_dir / f"{name}-dashboard.html"
        path.write_text(html, encoding="utf-8")
        return str(path)

    def _extract_html_block(self, text: str) -> str:
        match = re.search(r"```html\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _minimal_html_fallback(self, body: str) -> str:
        escaped = body.replace("<", "&lt;").replace(">", "&gt;")
        return (
            "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RAY Dashboard</title>"
            "<style>"
            ":root{--bg:#f5f7fb;--panel:#ffffff;--ink:#0f172a;--sub:#475569;--line:#e2e8f0;--accent:#0f766e;}"
            "*{box-sizing:border-box}body{margin:0;font-family:Georgia, 'Times New Roman', serif;"
            "background:radial-gradient(1200px 600px at 100% -10%,#dbeafe 0%,transparent 60%),var(--bg);color:var(--ink)}"
            ".shell{max-width:1000px;margin:2.5rem auto;padding:0 1rem}.card{background:var(--panel);border:1px solid var(--line);"
            "border-radius:16px;padding:1.25rem;box-shadow:0 18px 30px rgba(2,6,23,.06)}"
            "h1{font-size:1.3rem;margin:.1rem 0 .7rem 0}p{margin:.2rem 0 1rem 0;color:var(--sub);line-height:1.5}"
            "pre{white-space:pre-wrap;margin:0;background:#f8fafc;border:1px solid var(--line);padding:1rem;border-radius:12px;"
            "font:500 13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
            "</style></head><body><main class='shell'><section class='card'><h1>Autonomous Analysis Output</h1>"
            "<p>Generated fallback artifact with local formatting and preserved response content.</p>"
            f"<pre>{escaped}</pre></section></main></body></html>"
        )

    def _discover_urls(self, objective: str, limit: int = 3) -> List[str]:
        candidates = re.findall(r"https?://[^\s]+", objective, flags=re.IGNORECASE)
        if candidates:
            seen: List[str] = []
            for item in candidates:
                clean = item.strip().rstrip(")].,\"'")
                if clean and clean not in seen:
                    seen.append(clean)
            return seen[:limit]

        try:
            search_hits = self.clients.search_web(
                objective, max_results=max(limit + 2, 5)
            )
        except Exception:
            return []

        urls: List[str] = []
        for hit in search_hits:
            url = str(hit.get("url", "")).strip()
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
        return urls

    def _embedding_endpoints(self) -> list[str]:
        configured = settings.ollama_base_url.strip().rstrip("/")
        endpoints = [configured] if configured else []
        if "://ollama" in configured:
            endpoints.append(configured.replace("://ollama", "://localhost"))
        return [
            item
            for index, item in enumerate(endpoints)
            if item and item not in endpoints[:index]
        ]

    def _embed_query(self, query: str) -> list[float]:
        errors: list[str] = []
        for base in self._embedding_endpoints():
            for endpoint, payload in [
                (
                    "/api/embeddings",
                    {"model": settings.rag_embedding_model, "prompt": query},
                ),
                ("/api/embed", {"model": settings.rag_embedding_model, "input": query}),
            ]:
                try:
                    response = requests.post(base + endpoint, json=payload, timeout=60)
                    response.raise_for_status()
                    body = response.json()
                    embedding = body.get("embedding")
                    if (
                        not embedding
                        and isinstance(body.get("data"), list)
                        and body["data"]
                    ):
                        embedding = body["data"][0].get("embedding")
                    if (
                        not embedding
                        and isinstance(body.get("embeddings"), list)
                        and body["embeddings"]
                    ):
                        first = body["embeddings"][0]
                        if isinstance(first, list):
                            embedding = first
                    if not embedding:
                        raise RuntimeError(
                            "embedding vector missing in Ollama response"
                        )
                    return embedding
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{base}{endpoint}: {type(exc).__name__}: {exc}")
        raise RuntimeError("Ollama embeddings unavailable. " + " | ".join(errors))

    def _collection_names(self, client: Any) -> list[str]:
        names: list[str] = []
        try:
            rows = client.list_collections()
        except Exception:  # noqa: BLE001
            return names

        for row in rows or []:
            if isinstance(row, str):
                names.append(row)
                continue
            name = getattr(row, "name", "")
            if name:
                names.append(str(name))
                continue
            if isinstance(row, dict):
                dict_name = row.get("name")
                if dict_name:
                    names.append(str(dict_name))
        return names

    def _get_chroma_client(self) -> tuple[Any, str]:
        chromadb = importlib.import_module("chromadb")
        errors: list[str] = []

        try:
            remote = chromadb.HttpClient(
                host=settings.rag_chroma_host, port=settings.rag_chroma_port
            )
            remote.heartbeat()
            return remote, "http"
        except Exception as exc:  # noqa: BLE001
            errors.append(
                f"http://{settings.rag_chroma_host}:{settings.rag_chroma_port}: {type(exc).__name__}: {exc}"
            )

        try:
            local = chromadb.PersistentClient(path=str(self.rag_local_path))
            local.heartbeat()
            return local, "local"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{self.rag_local_path}: {type(exc).__name__}: {exc}")

        raise RuntimeError(" | ".join(errors))

    def _local_rag_search(self, query: str) -> str:
        if importlib.util.find_spec("chromadb") is None:
            return "Local RAG unavailable: chromadb package is not installed."

        try:
            client, backend = self._get_chroma_client()
            collection_names = self._collection_names(client)
            if settings.rag_collection_name not in collection_names:
                listed = ", ".join(collection_names) if collection_names else "none"
                return (
                    "Local RAG unavailable: collection "
                    f"'{settings.rag_collection_name}' not found in {backend} Chroma. Available: {listed}."
                )
            collection = client.get_collection(name=settings.rag_collection_name)
            embedding = self._embed_query(query)
            result = collection.query(
                query_embeddings=[embedding], n_results=settings.rag_top_k
            )
            documents = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]

            if not documents:
                return "No local RAG matches found in the configured collection."

            lines = []
            for index, content in enumerate(documents, start=1):
                source = ""
                if index - 1 < len(metadatas) and isinstance(
                    metadatas[index - 1], dict
                ):
                    source = metadatas[index - 1].get("source", "")
                prefix = f"[{index}]"
                if source:
                    prefix += f" ({source})"
                lines.append(prefix + " " + str(content).strip())
            return "\n\n".join(lines) + f"\n\n(RAG backend: {backend})"
        except Exception as exc:  # noqa: BLE001
            return f"Local RAG search failed: {type(exc).__name__}: {exc}"

    def _augment_objective_with_rag(self, objective: str) -> str:
        rag_context = self._local_rag_search(objective).strip()
        if not rag_context:
            return objective
        lower = rag_context.lower()
        if (
            lower.startswith("local rag unavailable")
            or lower.startswith("local rag search failed")
            or lower.startswith("no local rag matches")
        ):
            return objective

        return (
            "User objective:\n"
            + objective
            + "\n\nLocal RAG context (use if relevant and cite snippet ids like [1], [2]):\n"
            + rag_context
        )

    def _scrape_url(
        self,
        url: str,
        firecrawl_base_url_override: str | None = None,
        firecrawl_api_key_override: str | None = None,
    ) -> str:
        old_base_url = settings.firecrawl_base_url
        old_api_key = settings.firecrawl_api_key
        try:
            if firecrawl_base_url_override is not None:
                object.__setattr__(
                    settings, "firecrawl_base_url", firecrawl_base_url_override
                )
            if firecrawl_api_key_override is not None:
                object.__setattr__(
                    settings, "firecrawl_api_key", firecrawl_api_key_override
                )
            payload = self.clients.scrape_url(url)
            return json.dumps(payload, ensure_ascii=True)[:12000]
        except Exception as exc:  # noqa: BLE001
            return f"Web scrape unavailable: {type(exc).__name__}: {exc}"
        finally:
            object.__setattr__(settings, "firecrawl_base_url", old_base_url)
            object.__setattr__(settings, "firecrawl_api_key", old_api_key)

    def _fallback_run(
        self,
        objective: str,
        reason: str,
        system_prompt_override: str | None = None,
    ) -> Dict[str, Any]:
        grounded_objective = self._augment_objective_with_rag(objective)
        system_prompt = (
            system_prompt_override or settings.agentic_system_prompt
        ).strip() or settings.agentic_system_prompt
        answer = self.personal.ask(grounded_objective, system_prompt=system_prompt).get(
            "answer", ""
        )
        try:
            html = self.personal.visualize(answer, chart=settings.agentic_default_chart)
        except Exception:  # noqa: BLE001
            html = self._minimal_html_fallback(answer)
        artifact_path = self._save_html_artifact(objective, html)
        return {
            "status": "ok",
            "mode": "fallback",
            "reason": reason,
            "answer": answer,
            "visualization_artifact": artifact_path,
        }

    def _run_crewai(
        self,
        objective: str,
        model_override: str | None = None,
        litellm_base_url_override: str | None = None,
        litellm_api_key_override: str | None = None,
        firecrawl_base_url_override: str | None = None,
        firecrawl_api_key_override: str | None = None,
        system_prompt_override: str | None = None,
    ) -> Dict[str, Any]:
        crewai_module = importlib.import_module("crewai")
        crewai_tools_module = importlib.import_module("crewai.tools")

        Agent = getattr(crewai_module, "Agent")
        Crew = getattr(crewai_module, "Crew")
        LLM = getattr(crewai_module, "LLM")
        Process = getattr(crewai_module, "Process")
        Task = getattr(crewai_module, "Task")
        tool = getattr(crewai_tools_module, "tool")

        selected_model = (model_override or settings.litellm_model).strip()
        selected_base_url = (
            (litellm_base_url_override or settings.litellm_base_url).strip().rstrip("/")
        )
        selected_api_key = (
            litellm_api_key_override or settings.litellm_api_key
        ).strip()
        shared_directive = (
            system_prompt_override or settings.agentic_system_prompt
        ).strip() or settings.agentic_system_prompt

        llm = LLM(
            model=selected_model,
            base_url=selected_base_url,
            api_key=selected_api_key,
            temperature=0.0,
        )

        discovered_urls = self._discover_urls(objective, limit=3)
        objective_with_urls = objective
        if discovered_urls:
            objective_with_urls = (
                objective
                + "\n\nCandidate web sources (from prompt or DuckDuckGo):\n"
                + "\n".join(f"- {url}" for url in discovered_urls)
            )

        @tool("Firecrawl Scrape")
        def firecrawl_scrape(url: str) -> str:
            """Scrape a URL with Firecrawl and return compact JSON."""
            return self._scrape_url(
                url,
                firecrawl_base_url_override=firecrawl_base_url_override,
                firecrawl_api_key_override=firecrawl_api_key_override,
            )

        @tool("DuckDuckGo Search")
        def duckduckgo_search(query: str) -> str:
            """Search the web with DuckDuckGo and return compact JSON results."""
            try:
                return json.dumps(self.clients.search_web(query), ensure_ascii=True)[
                    :12000
                ]
            except Exception as exc:  # noqa: BLE001
                return f"DuckDuckGo search unavailable: {type(exc).__name__}: {exc}"

        @tool("Local Document Search")
        def local_document_search(query: str) -> str:
            """Search the local Chroma RAG collection and return top matches."""
            return self._local_rag_search(query)

        researcher = Agent(
            role="Lead Data Synthesizer",
            goal=(
                "Gather grounded evidence from local RAG and web scraping, then summarize facts. "
                + shared_directive
            ),
            backstory=(
                "You are a strict researcher who cites context and avoids unsupported claims. "
                "You explicitly mark unknowns when data is missing."
            ),
            tools=[duckduckgo_search, firecrawl_scrape, local_document_search],
            llm=llm,
            allow_delegation=False,
            verbose=False,
        )

        visualizer = Agent(
            role="Frontend Visualization Developer",
            goal=(
                "Convert validated findings into an interactive HTML dashboard artifact while preserving factual accuracy."
            ),
            backstory="You write clean single-file HTML with embedded JS and clear labels.",
            llm=llm,
            allow_delegation=False,
            verbose=False,
        )

        research_task = Task(
            description=(
                "System directive:\n" + shared_directive + "\n\n"
                "Objective:\n"
                "{objective}\n\n"
                "Use tools as needed. Prefer local RAG first, then web scraping for missing context. "
                "If the user did not provide URLs, run DuckDuckGo Search first and then scrape top results. "
                "Return concise findings with explicit evidence bullets."
            ),
            expected_output=(
                "A factual summary with sections: Findings, Evidence, and Gaps. "
                "Do not invent data."
            ),
            agent=researcher,
        )

        visualization_task = Task(
            description=(
                "Based on the research output, produce:\n"
                "1) A concise answer for the user.\n"
                "2) A single ```html``` code block for an interactive visualization dashboard."
            ),
            expected_output=("A final narrative answer and one HTML code block only."),
            agent=visualizer,
            context=[research_task],
        )

        crew = Crew(
            agents=[researcher, visualizer],
            tasks=[research_task, visualization_task],
            process=Process.sequential,
            verbose=False,
        )

        outcome = crew.kickoff(inputs={"objective": objective_with_urls})
        outcome_text = str(outcome)
        html = self._extract_html_block(outcome_text)
        if not html:
            try:
                html = self.personal.visualize(
                    outcome_text, chart=settings.agentic_default_chart
                )
            except Exception:  # noqa: BLE001
                html = self._minimal_html_fallback(outcome_text)

        artifact_path = self._save_html_artifact(objective, html)
        return {
            "status": "ok",
            "mode": "crewai",
            "answer": outcome_text,
            "visualization_artifact": artifact_path,
        }

    def run_goal(
        self,
        objective: str,
        model_override: str | None = None,
        litellm_base_url_override: str | None = None,
        litellm_api_key_override: str | None = None,
        firecrawl_base_url_override: str | None = None,
        firecrawl_api_key_override: str | None = None,
        enable_crewai_override: bool | None = None,
        system_prompt_override: str | None = None,
    ) -> Dict[str, Any]:
        objective = (objective or "").strip()
        if not objective:
            return {"status": "error", "detail": "Objective is required."}

        stack_ready = importlib.util.find_spec("crewai") is not None

        crew_enabled = (
            settings.agentic_enable_crewai
            if enable_crewai_override is None
            else bool(enable_crewai_override)
        )

        if not crew_enabled:
            return self._fallback_run(
                objective,
                "CrewAI disabled by AGENTIC_ENABLE_CREWAI=false.",
                system_prompt_override=system_prompt_override,
            )

        if not stack_ready:
            return self._fallback_run(
                objective,
                "CrewAI stack is not installed. Install requirements-agentic.txt to enable autonomous crews.",
                system_prompt_override=system_prompt_override,
            )

        try:
            return self._run_crewai(
                objective,
                model_override=model_override,
                litellm_base_url_override=litellm_base_url_override,
                litellm_api_key_override=litellm_api_key_override,
                firecrawl_base_url_override=firecrawl_base_url_override,
                firecrawl_api_key_override=firecrawl_api_key_override,
                system_prompt_override=system_prompt_override,
            )
        except Exception as exc:  # noqa: BLE001
            return self._fallback_run(
                objective,
                f"CrewAI execution failed: {type(exc).__name__}: {exc}",
                system_prompt_override=system_prompt_override,
            )


if __name__ == "__main__":
    fire.Fire(AgenticOrchestrator)
