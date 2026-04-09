# Agentic CrewAI + Chainlit Workspace

> Historical setup note. The current primary app is `godmode-agent` with a FastAPI backend and React/Vite frontend. This document describes an older Chainlit-first setup.

This repository is now configured as a Chainlit-first autonomous workspace.

## Stack Layout

- `LiteLLM` in Docker: local OpenAI-compatible router on `http://localhost:4000/v1`
- `Ollama` in Docker: local embedding/model runtime
- `ChromaDB` in Docker: local vector store
- `Chainlit` (Python app): custom UI canvas with inline runtime scoreboards
- `CrewAI` (Python): autonomous multi-agent orchestration

## Core Files

- `app/chainlit_app.py`: custom Chainlit app with persistent local memory and inline elements.
- `agents/agentic_orchestrator.py`: CrewAI-first orchestrator with fallback safety.
- `scripts/start_chainlit.sh`: launch the custom Chainlit interface.
- `scripts/start_docker_stack.sh`: launch LiteLLM + ChromaDB + Ollama.
- `requirements-agentic.txt`: optional CrewAI/LangChain dependency pack.

## Environment

Configure these in `.env`:

- `LITELLM_BASE_URL` (default `http://localhost:4000/v1`)
- `LITELLM_MASTER_KEY`
- `LITELLM_API_KEY`
- `LITELLM_MODEL`
- `RAG_CHROMA_HOST` / `RAG_CHROMA_PORT`
- `RAG_COLLECTION_NAME`
- `RAG_EMBEDDING_MODEL`
- `RAG_TOP_K`
- `FIRECRAWL_BASE_URL` (set to local self-host when running Firecrawl self-host)
- `FIRECRAWL_API_KEY` (can stay empty for local self-host setups)
- `CHAINLIT_HOST` / `CHAINLIT_PORT`

## Boot Sequence

```bash
scripts/start_docker_stack.sh
scripts/install_agentic_stack.sh
scripts/start_chainlit.sh
```

Single-command option:

```bash
scripts/start_chainlit_workspace.sh
```

Default Chainlit URL: `http://localhost:8001`

## Quick Validation

```bash
scripts/run_agentic_goal.sh "Compare local RAG context with current web coverage and draft a dashboard"
```

## Failure Safety

If CrewAI is unavailable or a run fails, the orchestrator falls back to the existing local agent stack and still returns a response plus a visualization artifact in `data/artifacts`.
