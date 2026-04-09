# RAY Agentic Workspace

RAY is a local-first agent workspace centered on the `godmode-agent` app: a FastAPI backend plus a React/Vite frontend, with LangGraph orchestration, LiteLLM routing, Ollama embeddings, and local/remote vector stores.

## 100% Free & Local-First Architecture
This architecture is designed to cost **$0/month** by leveraging powerful local tools and generous free cloud tiers:
* **Web Scraping:** Uses **Crawl4AI** locally (via Playwright) instead of paid APIs like Firecrawl.
* **Web Search:** Uses **DuckDuckGo** (Free) for discovering URLs.
* **LLM Reasoning:** Uses **Groq's Free Tier** (e.g. `llama-3.3-70b-versatile`) for orchestration, planning, and summarization.
* **Local Fallback:** Uses **Ollama** for fallback LLM generation.
* **Embeddings & Vector DB:** Uses **Ollama embeddings** and a self-hosted **Qdrant** Docker container, keeping your data entirely local and free from API costs.

## Core Capabilities
* **Autonomous Web Research:** Basic RAG via web search, and "Deep Research Mode" for complex, multi-page asynchronous scraping.
* **Continuous Learning (RL Feedback):** The agent learns from your corrections via the `/api/feedback` endpoint, permanently storing preferences in the `behavior_index` (Qdrant).
* **Document Processing:** Ingests local files and PDFs for instant semantic search.
* **Advanced Orchestration:** Intent routing, multi-step planning, and rigorous claim verification (using ReLU scoring to prevent hallucinations).

## Skills & Visual Artifacts
While the base agent orchestrates research, RAY includes an extensible **Skills Framework** (`core/skills/`). 
Because basic LLMs often struggle with producing high-quality complex visual artifacts (like code, complex diagrams, or full React components), you can inject specialized logic into the pipeline:
* Generate **React Components** via `react_component` skill.
* Generate advanced **Mermaid.js** diagrams via `mermaid_diagram` skill.
* Easily extend the `core/skills/__init__.py` file to add custom integrations, Python-based generators, or better artifact templates.

## Primary App

- Backend: `godmode-agent/apps/api/server.py`
- Frontend: `godmode-agent/apps/web`
- Orchestrator: `core/graph.py`
- Runtime start script: `scripts/start_app.sh`

## Quick Start

```bash
./scripts/bootstrap.sh
./scripts/install_agentic_stack.sh
./scripts/start_app.sh
```

Services:

- API: `http://localhost:8002`
- Web UI: `http://localhost:5173`

## Tests

Primary app checks:

```bash
cd godmode-agent
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest tests -q
cd apps/web && npm run build
```

## Notes

- `scripts/start_app.sh` prefers the root `.venv`, which is the supported Python environment for this repo.
- If you want the current runtime architecture, read `ARCHITECTURE.md` first.
