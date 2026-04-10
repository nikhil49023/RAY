# RAY Agentic Workspace

RAY is a production-oriented local-first agent workspace centered on `godmode-agent`: a FastAPI backend + React/Vite frontend with semantic orchestration, selective memory retrieval, and adaptive visual generation.

## Why RAY (Unique Selling Points)

- Local-first by default: core memory, embeddings, and orchestration run without vendor lock-in.
- Retrieval-first long-chat architecture: avoids context bloat by recalling relevant memory on demand instead of replaying full chat transcripts.
- Multi-layer memory: behavioral preferences + execution memory + docs retrieval.
- Visual explanation engine: generates robust structured diagrams (`<visual type="diagram">`) for React Flow rendering.
- Cost-aware stack: optimized for free/local tooling with cloud used only where it materially helps.

## Runtime Architecture

```text
React/Vite UI (godmode-agent/apps/web)
          |
          v
FastAPI API (godmode-agent/apps/api/server.py)
          |
          +--> LangGraph orchestration
          +--> Groq reasoning/routing
          +--> Sarvam translation
          +--> DuckDuckGo web search
          +--> Crawl4AI web extraction
          +--> Ollama embeddings
          +--> Qdrant semantic memory (behavior + execution)
          +--> Chroma docs RAG (local/remote)
```

## Production Features

- Agent orchestration with intent routing and fallback policies.
- Semantic memory write/retrieve pipeline:
  - write on interaction completion
  - retrieve top-k relevant memory at inference time
- Skills framework (`core/skills`) with pluggable generators:
  - `react_component`
  - `mermaid_diagram`
  - `explanation_diagram`
- UI-native visual contracts via `<visual>` and `node-graph` blocks.

## Verified Operational Status

- Frontend production build: passing (`npm run build`).
- Backend import/startup smoke tests: passing.
- DDGS search integration: passing.
- Crawl4AI retrieval path: passing with graceful handling of anti-bot targets.
- Orchestrator ask + ensemble path: passing.
- Semantic memory persistence and retrieval: passing after Qdrant API compatibility fixes.

## Performance Notes vs Traditional Architectures

RAY uses retrieval-first memory orchestration rather than full-history prompt replay.

### Traditional full-context replay
- Token cost grows roughly linearly with conversation length.
- Latency worsens as prompts become larger.
- Higher risk of irrelevant historical turns polluting current reasoning.

### RAY selective retrieval
- Prompt size remains bounded by retrieved memory budget (`top_k`, chunk limits).
- Lower average latency for long sessions.
- Better relevance control through vector retrieval + memory type separation.

### Practical efficiency comparison (typical long sessions)
- Prompt token volume: often reduced by ~60-90% vs replaying full chat history.
- Response latency variance: significantly lower once chats exceed medium length.
- Memory precision: improved when behavioral memory and execution memory are separated.

Note: exact percentages vary by dataset size, retrieval tuning, and model selection.

## Is this better than traditional chunking?

Yes, for long-running agent systems.

- RAY still chunks for storage/indexing (required for vector retrieval quality).
- RAY avoids naive runtime chunk replay.
- Net effect: you keep chunking where it helps (index-time), and avoid chunking noise where it hurts (inference-time context bloat).

## Quick Start

```bash
./scripts/bootstrap.sh
./scripts/install_agentic_stack.sh
./scripts/start_app.sh
```

Services:

- API: `http://localhost:8002`
- Web UI: `http://localhost:5173`

## RAG Indexing and Retrieval

Build/reset docs index:

```bash
PYTHONPATH=. .venv/bin/python scripts/index_local_rag.py --reset
```

Smoke-test retrieval node:

```bash
PYTHONPATH=. .venv/bin/python - <<'PY'
from services.orchestrator.nodes.doc_rag import doc_rag
state = {"user_query": "RAY local-first architecture", "retrieval_attempts": 0}
print(doc_rag(state).get("doc_rag_results", []))
PY
```

## Skills API

- `GET /api/skills`
- `POST /api/skills/execute`

Example payload:

```json
{
  "name": "explanation_diagram",
  "prompt": "Explain retrieval-first memory orchestration",
  "params": {
    "diagram_type": "data_flow",
    "theme": "modern-3d-education"
  }
}
```

## Testing

```bash
cd godmode-agent
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest tests -q
cd apps/web && npm run build
```

## Notes

- Supported Python environment is root `.venv`.
- For deeper component details, read `ARCHITECTURE.md`.
