# RAY → God Mode Agent (LangGraph Migration)

Complete migration from CrewAI to LangGraph for production-grade autonomous agents.

## Architecture

### Core Components

1. **LangGraph State Machine** (`services/orchestrator/graph.py`)
   - 8-node execution graph
   - Conditional edges for verification retry
   - SQLite checkpointing for resume capability

2. **Memory System** (`services/memory/`)
   - 3 collections: docs, behavior, execution
   - Mem0-style layered retrieval
   - Promotion rules for persistent preferences

3. **Inline UI** (`apps/ui-chainlit/public/elements/`)
   - ScoreCard: Runtime health
   - EvidenceTable: Claim-to-source mapping
   - ResearchTimeline: Node progress
   - DashboardPanel: Inline charts
   - MemoryBadge: Applied preferences

4. **Artifact Workers** (`services/workers/`)
   - PDF, DOCX, XLSX, Chart generation
   - Structured state → downloadable outputs

## Execution Flow

```
User Query
    ↓
Intent Router → Memory Prefetch → Planner
    ↓                                ↓
    ↓                          Doc RAG ⟷ Web RAG
    ↓                                ↓
    ↓                            Verifier
    ↓                                ↓
    ↓                    [FAILED] → Retry Retrieval
    ↓                                ↓
    ↓                    [PASSED] → Composer
    ↓                                ↓
    ↓                        Memory Writeback
    ↓                                ↓
Final Answer + Evidence + Artifacts
```

## Installation

```bash
# Install dependencies
./scripts/install_langgraph.sh

# Start services
./scripts/start_docker_stack.sh

# Run tests
python tests/test_graph_execution.py
python tests/test_memory_promotion.py
python tests/test_verifier_coverage.py

# Start Chainlit
chainlit run apps/ui-chainlit/app.py -w
```

## Usage

### LangGraph Mode (Default)

```python
from services.orchestrator.langgraph_orchestrator import LangGraphOrchestrator

orchestrator = LangGraphOrchestrator()

result = orchestrator.run(
    query="Research LangGraph benefits for production agents",
    session_id="user_123",
    model_name="premium-thinker"
)

print(result["answer"])
print(f"Evidence: {len(result['evidence'])} sources")
print(f"Applied rules: {result['applied_rules']}")
```

### Chat Commands

- `/langgraph` - Switch to LangGraph mode
- `/crewai` - Switch to CrewAI fallback mode

## Configuration

### Graph Execution (`configs/graph.yaml`)

```yaml
graph:
  checkpoint_path: "data/checkpoints/graph.db"
  max_retries: 3
  
verification:
  min_evidence:
    research: 2
    artifact: 1
    chat: 0
```

### Memory (`configs/memory.yaml`)

```yaml
collections:
  docs_index: "ray_docs"
  behavior_index: "ray_behavior"
  execution_index: "ray_execution"

promotion_rules:
  persistent_signals: ["always", "never", "prefer"]
  ephemeral_signals: ["today", "right now"]
```

## Non-Negotiable Rules

1. **Local GPU = embeddings only**
   - Ollama handles embeddings
   - LiteLLM routes reasoning to free providers

2. **No answer before verification**
   - Graph enforces: `verifier → composer` only if `PASSED`

3. **Artifacts from structured state**
   - Workers accept typed objects, not raw text

4. **Behavioral memory retrieved first**
   - Graph order: `intent_router → memory_prefetch → planner`

5. **Inline UI default**
   - All JSX elements use `display="inline"`

## Testing

```bash
# Full test suite
python -m pytest tests/ -v

# Individual tests
python tests/test_graph_execution.py
python tests/test_memory_promotion.py
python tests/test_verifier_coverage.py
```

## Migration from CrewAI

The system supports parallel operation:

```python
# In Chainlit app
if use_langgraph:
    result = langgraph_orchestrator.run(query)
else:
    result = crewai_orchestrator.run(query)  # Fallback
```

Remove CrewAI after Phase 4 validation.

## File Structure

```
RAY/
├── services/
│   ├── orchestrator/
│   │   ├── graph.py                    # LangGraph state machine
│   │   ├── state.py                    # AgentState schema
│   │   ├── langgraph_orchestrator.py   # Main orchestrator
│   │   ├── nodes/                      # 8 graph nodes
│   │   └── policies/                   # Retry + fallback
│   ├── memory/
│   │   ├── retriever.py                # Mem0-style retrieval
│   │   ├── embedder.py                 # Ollama embeddings
│   │   ├── promotion_rules.py          # Memory filtering
│   │   └── stores/                     # 3 collections
│   └── workers/                        # Artifact generation
├── apps/ui-chainlit/
│   ├── app.py                          # Chainlit integration
│   └── public/elements/                # JSX components
├── configs/
│   ├── graph.yaml                      # Execution policies
│   └── memory.yaml                     # Memory config
└── tests/                              # Test suite
```

## Performance

- **Chat**: ~2-3s (async checkpoint)
- **Research**: ~10-15s (sync checkpoint, evidence collection)
- **Artifact**: ~5-8s (sync checkpoint, worker execution)

## Troubleshooting

### Graph execution fails

```bash
# Check checkpoint database
ls -lh data/checkpoints/graph.db

# Reset checkpoints
rm data/checkpoints/graph.db
```

### Memory not persisting

```bash
# Check Chroma collections
python -c "from services.memory.stores.behavior_index import BehaviorIndex; print(BehaviorIndex().status())"
```

### Verification always fails

```bash
# Check RAG collection exists
python -c "from services.memory.stores.docs_index import DocsIndex; print(DocsIndex().query('test'))"
```

## Next Steps

1. **Phase 1 Complete**: LangGraph core + LiteLLM integration ✅
2. **Phase 2 Complete**: Mem0-style memory system ✅
3. **Phase 3 Complete**: Inline UI + artifact workers ✅
4. **Phase 4 Complete**: Verification + reliability ✅

**Production Ready**: Deploy with confidence.

## License

Same as RAY project.
