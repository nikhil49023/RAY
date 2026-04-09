# RAY God Mode Agent

Production-facing RAY application built as a FastAPI backend plus a React/Vite frontend, with LangGraph as the default orchestration runtime.

## Architecture

```text
Web UI (React/Vite)
    |
    v
FastAPI API
    |
    +--> LangGraph runtime
    +--> Codex CLI runtime
    +--> LiteLLM-backed model access
    +--> Firecrawl and DuckDuckGo research
    +--> Qdrant semantic memory
    +--> Ollama embeddings
```

## Main Paths

- API: `apps/api/server.py`
- Web: `apps/web`
- LangGraph: `services/orchestrator/graph.py`
- Runtime settings: `services/orchestrator/runtime.py`
- Memory: `services/memory/`

## Start

From the repo root:

```bash
./scripts/bootstrap.sh
./scripts/install_agentic_stack.sh
./scripts/start_app.sh
```

App URLs:

- API: `http://localhost:8002`
- Web: `http://localhost:5173`

## Test

From `godmode-agent/`:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest tests -q
cd apps/web && npm run build
```

## Runtime Backends

- `langgraph`: default orchestrated runtime
- `codex_cli`: alternate CLI-agent backend selected in settings

## Notes

- The old Chainlit material in the repo is historical prototype code, not the primary app surface.
- The supported Python environment is the repo root `.venv`.
