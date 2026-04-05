# RAY Agentic Workspace (Chainlit First)

Custom autonomous workspace built with Chainlit + CrewAI + LiteLLM + Ollama + Chroma.

## Core Features

- Chainlit custom UI with inline runtime scoreboard, gauges, and artifact previews.
- CrewAI orchestrator for autonomous tool use (RAG + Firecrawl + visualization).
- Runtime model selection from chat settings.
- Runtime API/base URL overrides for LiteLLM and Firecrawl.
- Behavioral reinforcement memory (RAG-backed) persisted in Chroma + `data/memory/behavior_rules.jsonl`.
- Local conversation history persisted in `data/memory/chainlit_history.jsonl`.

## Services

- LiteLLM router: `http://localhost:4000`
- ChromaDB: `http://localhost:8000`
- Ollama: container service (used by app)
- Chainlit UI: `http://localhost:8001`

## Start

```bash
scripts/start_docker_stack.sh
scripts/install_agentic_stack.sh
scripts/start_langgraph_workspace.sh
```

Or single command:

```bash
scripts/start_app.sh
```

## Local RAG Index

Populate Chroma collection (`RAG_COLLECTION_NAME`, default `ray_docs`) from local markdown docs:

```bash
./.venv/bin/python scripts/index_local_rag.py --reset
```

## Chat Settings in UI

Use the Chainlit settings panel to configure:

- `Primary Model` from available aliases and known models.
- `Custom Model` (optional) to override selection.
- `System Prompt` for crew/fallback behavior control.
- `Behavior Memory`, `Behavior Memory Top K`, and `Auto Capture Feedback`.
- `Dashboard Style` for runtime telemetry visuals.
- `LiteLLM Base URL` and `LiteLLM API Key`.
- `Firecrawl Base URL` and optional `Firecrawl API Key`.
- DuckDuckGo is used for URL discovery when no explicit links are provided.
- `Enable CrewAI` switch.
- Theme: `system`, `light`, `dark`.

## Firecrawl Self-Host

Start Firecrawl self-host stack:

```bash
scripts/start_firecrawl_selfhost.sh
```

Then set in chat settings:

- `Firecrawl Base URL`: `http://localhost:3002`
- `Firecrawl API Key`: optional/blank when self-host policy allows no auth.

## Notes

- If `RAG_COLLECTION_NAME` (default `ray_docs`) does not exist, RAG tool will return a clear availability message.
- If CrewAI execution fails, the app falls back to the local agent pipeline and still returns an artifact path.
