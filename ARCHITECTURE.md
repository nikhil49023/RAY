# RAY Architecture

## Current Runtime

The current app is `godmode-agent`, not the older Chainlit prototype.

```text
React/Vite Web UI (godmode-agent/apps/web)
                |
                v
FastAPI API (godmode-agent/apps/api/server.py)
                |
                v
LangGraph Orchestrator (godmode-agent/services/orchestrator/graph.py)
                |
                +--> LiteLLM-routed chat/reasoning
                +--> DuckDuckGo + Firecrawl research
                +--> Qdrant execution + behavioral memory
                +--> Ollama embeddings
```

## Main Components

### Web App

- React 19 + Vite frontend in `godmode-agent/apps/web`
- Talks to the FastAPI backend at `/api/*`
- Renders chat, settings, artifacts, research sessions, and visual outputs

### API Server

- FastAPI app in `godmode-agent/apps/api/server.py`
- Persists threads, artifacts, and research sessions under `godmode-agent/data/`
- Exposes settings, models, chat, artifact, thread, and research endpoints
- Supports both `langgraph` and `codex_cli` agent runtimes via persisted runtime settings

### Orchestration

- Primary orchestrator lives in `godmode-agent/services/orchestrator/graph.py`
- Flow is summarizer -> memory_prefetch -> intent_router -> planner -> optional web research -> composer -> memory_writeback
- `langgraph` is the default backend
- `codex_cli` is an alternate runtime selected through settings

### Memory

- Qdrant-backed semantic memory under `godmode-agent/services/memory/`
- Behavioral memory, execution history, and retrieval helpers are used by the primary app
- Top-level Chroma-backed memory under `services/memory/` remains part of the older prototype path

## Repo Split

### Primary

- `godmode-agent/`: production-facing FastAPI + React application
- `scripts/start_app.sh`: supported launcher
- root `.venv`: supported Python environment for repo scripts and tests

### Prototype / Migration Artifacts

- `apps/ui-chainlit/`: older UI prototype
- top-level `services/`: earlier LangGraph prototype
- top-level docs describing Chainlit or inline JSX elements should be read as migration history unless updated to say otherwise

## Operational Notes

- Prefer `./scripts/bootstrap.sh` then `./scripts/install_agentic_stack.sh` before running the app
- `scripts/start_app.sh` starts Docker services, FastAPI on `8002`, and Vite on `5173`
- The repo currently supports hybrid usage of LangGraph orchestration plus lower-level LangChain integrations inside nodes and helpers
