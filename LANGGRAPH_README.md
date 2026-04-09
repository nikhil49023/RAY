# LangGraph Notes

This repo contains two LangGraph codepaths:

1. `godmode-agent/services/orchestrator/graph.py`
2. `services/orchestrator/graph.py`

The primary app uses the first path under `godmode-agent/`.

## Primary LangGraph Runtime

- Graph: `godmode-agent/services/orchestrator/graph.py`
- Runtime config: `godmode-agent/services/orchestrator/runtime.py`
- API entrypoint: `godmode-agent/apps/api/server.py`

Execution shape:

```text
summarizer
  -> memory_prefetch
  -> intent_router
  -> planner
  -> web_rag / deep_research when needed
  -> composer
  -> memory_writeback
```

## Prototype LangGraph Runtime

- Graph: `services/orchestrator/graph.py`
- Wrapper: `services/orchestrator/langgraph_orchestrator.py`
- Tests: `tests/test_graph_execution.py`

This path is still useful for isolated experimentation and regression checks, but it is not the main app entrypoint.

## Install

```bash
./scripts/bootstrap.sh
./scripts/install_agentic_stack.sh
```

## Verify

```bash
.venv/bin/python tests/test_memory_promotion.py
.venv/bin/python tests/test_verifier_coverage.py
.venv/bin/python tests/test_graph_execution.py

cd godmode-agent
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest tests -q
```

## Run

```bash
./scripts/start_app.sh
```

Endpoints:

- API: `http://localhost:8002`
- Web: `http://localhost:5173`
