# RAY → God Mode Agent: LangGraph Migration Roadmap

## Overview
Migrate from CrewAI to LangGraph while keeping LiteLLM, Chainlit, and local-first architecture.

---

## Phase 1: Control Plane (Days 1-6)

### Day 1: LangGraph Foundation
**Goal**: Replace CrewAI orchestrator with LangGraph state machine

```bash
# Install dependencies
pip install langgraph langchain-core langchain-community langgraph-checkpoint-sqlite
```

**Files to create**:
- `services/orchestrator/state.py` - Define AgentState TypedDict
- `services/orchestrator/graph.py` - Build StateGraph with 8 nodes
- `services/orchestrator/nodes/intent_router.py` - Classify request type

**Migration**: Keep existing `agents/agentic_orchestrator.py` as fallback, add LangGraph path.

### Day 2: Core Nodes
**Files to create**:
- `services/orchestrator/nodes/planner.py` - Structured plan generation
- `services/orchestrator/nodes/composer.py` - Final answer assembly
- `services/orchestrator/nodes/verifier.py` - Evidence validation

**Test**: Run graph with mock state, verify node transitions.

### Day 3: Persistence Layer
**Goal**: Add checkpointing for resume capability

```bash
# SQLite for execution state
```

**Files to create**:
- `services/orchestrator/checkpointer.py` - SQLite checkpoint config
- `configs/graph.yaml` - Graph execution policies

**Update**: Wire checkpointer into graph compilation.

### Day 4: LiteLLM Integration
**Goal**: Connect graph nodes to existing LiteLLM proxy

**Files to update**:
- `services/orchestrator/nodes/planner.py` - Use LiteLLM via langchain
- `services/orchestrator/nodes/composer.py` - Same

**Keep**: Existing `app/litellm_config.yaml` and proxy setup.

### Day 5: Parallel Execution
**Goal**: Add parallel RAG + web retrieval nodes

**Files to create**:
- `services/orchestrator/nodes/doc_rag.py` - Existing RAG tool wrapper
- `services/orchestrator/nodes/web_rag.py` - Firecrawl wrapper

**Update**: Graph to run doc_rag and web_rag in parallel after planner.

### Day 6: Fallback Policies
**Files to create**:
- `services/orchestrator/policies/retry.py` - Retry logic for failed nodes
- `services/orchestrator/policies/fallback.py` - Provider fallback via LiteLLM

**Test**: Trigger failures, verify retry and fallback behavior.

---

## Phase 2: Memory System (Days 7-11)

### Day 7: Memory Schema Split
**Goal**: Separate docs, behavior, execution into 3 collections

**Files to create**:
- `services/memory/schemas.py` - Preference, Constraint, Correction, ProjectState
- `services/memory/stores/docs_index.py` - Wrap existing RAG collection
- `services/memory/stores/behavior_index.py` - New Chroma collection
- `services/memory/stores/execution_index.py` - New Chroma collection

**Migration**: Keep `data/chroma` structure, add two new collections.

### Day 8: Mem0-Style Retrieval
**Goal**: Retrieve user memory first, merge with session memory

**Files to create**:
- `services/memory/retriever.py` - Multi-collection retrieval with ranking
- `services/orchestrator/nodes/memory_prefetch.py` - Pre-prompt injection node

**Update**: Graph to call memory_prefetch before planner.

### Day 9: Memory Extraction
**Goal**: Extract preferences/corrections after each interaction

**Files to create**:
- `services/memory/extract_preferences.py` - LLM-based extraction
- `services/orchestrator/nodes/memory_writeback.py` - Final graph node

**Update**: Graph to call memory_writeback after composer.

### Day 10: Ollama Embeddings
**Goal**: Use local Ollama for all embedding tasks

**Files to update**:
- `services/memory/embedder.py` - Switch to Ollama embedding model
- `agents/rag_tool.py` - Use new embedder

**Keep**: Existing Ollama container setup.

### Day 11: Promotion Rules
**Goal**: Only persist stable preferences, not ephemeral facts

**Files to create**:
- `services/memory/promotion_rules.py` - Filter logic for user vs session memory

**Update**: memory_writeback to apply promotion rules before storing.

---

## Phase 3: UI & Artifacts (Days 12-18)

### Day 12: Custom Element Scaffold
**Goal**: Create JSX components for inline rendering

**Files to create**:
- `apps/ui-chainlit/public/elements/ScoreCard.jsx`
- `apps/ui-chainlit/public/elements/EvidenceTable.jsx`
- `apps/ui-chainlit/public/elements/ResearchTimeline.jsx`
- `apps/ui-chainlit/public/elements/DashboardPanel.jsx`

**Test**: Render each element with mock props from Python.

### Day 13: ScoreCard Integration
**Goal**: Replace Plotly scoreboard with inline ScoreCard

**Files to update**:
- `app/chainlit_app.py` - Remove `_scoreboard()`, add ScoreCard element

**Keep**: Same readiness checks, new rendering.

### Day 14: Evidence Table
**Goal**: Show claim → source mapping inline

**Files to create**:
- `services/orchestrator/evidence.py` - Evidence object schema

**Update**: Verifier node to produce evidence objects, composer to render EvidenceTable.

### Day 15: Research Timeline
**Goal**: Stream node progress into chat

**Files to update**:
- `services/orchestrator/graph.py` - Add streaming callback
- `app/chainlit_app.py` - Update ResearchTimeline element during execution

**Test**: Watch timeline update as graph executes.

### Day 16: Artifact Workers
**Goal**: Consolidate PDF/DOCX/XLSX generation

**Files to create**:
- `services/workers/pdf_worker.py`
- `services/workers/docx_worker.py`
- `services/workers/xlsx_worker.py`
- `services/workers/chart_worker.py`

**Migration**: Move logic from existing artifact code, standardize interface.

### Day 17: Dashboard Panel
**Goal**: Inline charts instead of separate Plotly figures

**Files to update**:
- `app/chainlit_app.py` - Replace Plotly with DashboardPanel element

**Keep**: Same chart data, new rendering.

### Day 18: Memory Badge
**Goal**: Show which preferences were applied

**Files to create**:
- `apps/ui-chainlit/public/elements/MemoryBadge.jsx`

**Update**: memory_prefetch to return applied rules, render badge inline.

---

## Phase 4: Reliability (Days 19-23)

### Day 19: Verifier Rules
**Goal**: Enforce evidence coverage before final answer

**Files to update**:
- `services/orchestrator/nodes/verifier.py` - Add coverage checks
- `services/orchestrator/graph.py` - Add conditional edge: verifier → retrieval if FAILED

**Test**: Submit query with no sources, verify loop back to retrieval.

### Day 20: Provider Fallback
**Goal**: Auto-fallback on rate limits via LiteLLM

**Files to update**:
- `app/litellm_config.yaml` - Add fallback routing
- `services/orchestrator/policies/fallback.py` - Wrap LiteLLM calls

**Test**: Trigger rate limit, verify fallback to secondary provider.

### Day 21: Checkpointing Modes
**Goal**: Sync durability for research, async for chat

**Files to update**:
- `services/orchestrator/checkpointer.py` - Add mode selection
- `services/orchestrator/nodes/intent_router.py` - Set checkpoint mode by intent

**Test**: Interrupt research job, resume from checkpoint.

### Day 22: Error Recovery
**Goal**: Graceful degradation when tools fail

**Files to update**:
- `services/orchestrator/nodes/doc_rag.py` - Return empty on failure
- `services/orchestrator/nodes/web_rag.py` - Same
- `services/orchestrator/nodes/composer.py` - Handle partial evidence

**Test**: Kill Firecrawl, verify answer still generated from RAG only.

### Day 23: Integration Test Suite
**Files to create**:
- `tests/test_graph_execution.py` - End-to-end graph run
- `tests/test_memory_promotion.py` - Verify promotion rules
- `tests/test_verifier_coverage.py` - Evidence validation
- `tests/test_ui_streaming.py` - Timeline updates

**Run**: Full test suite, fix failures.

---

## Migration Commands

### Start New Stack
```bash
# Phase 1
scripts/start_docker_stack.sh  # Keep existing
pip install langgraph langchain-core langgraph-checkpoint-sqlite

# Phase 2
python scripts/init_memory_collections.py  # Create behavior_index, execution_index

# Phase 3
cd apps/ui-chainlit && npm install  # For JSX compilation

# Phase 4
pytest tests/ -v  # Run full suite
```

### Parallel Operation
Keep CrewAI path active during migration:
```python
# In chainlit_app.py
if cl.user_session.get("enable_langgraph"):
    result = langgraph_orchestrator.run(...)
else:
    result = crewai_orchestrator.run(...)  # Fallback
```

Remove CrewAI after Phase 4 validation.

---

## File Structure (Final)

```
RAY/
├── apps/
│   └── ui-chainlit/
│       ├── app.py (migrated from app/chainlit_app.py)
│       └── public/elements/
│           ├── ScoreCard.jsx
│           ├── EvidenceTable.jsx
│           ├── ResearchTimeline.jsx
│           ├── DashboardPanel.jsx
│           └── MemoryBadge.jsx
├── services/
│   ├── orchestrator/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── checkpointer.py
│   │   ├── evidence.py
│   │   ├── nodes/
│   │   │   ├── intent_router.py
│   │   │   ├── memory_prefetch.py
│   │   │   ├── planner.py
│   │   │   ├── doc_rag.py
│   │   │   ├── web_rag.py
│   │   │   ├── verifier.py
│   │   │   ├── composer.py
│   │   │   └── memory_writeback.py
│   │   └── policies/
│   │       ├── retry.py
│   │       └── fallback.py
│   ├── memory/
│   │   ├── embedder.py
│   │   ├── retriever.py
│   │   ├── extract_preferences.py
│   │   ├── promotion_rules.py
│   │   ├── schemas.py
│   │   └── stores/
│   │       ├── docs_index.py
│   │       ├── behavior_index.py
│   │       └── execution_index.py
│   ├── tools/
│   │   ├── firecrawl_client.py (keep)
│   │   ├── code_runner.py (keep)
│   │   ├── artifact_writer.py (keep)
│   │   └── image_client.py (keep)
│   └── workers/
│       ├── pdf_worker.py
│       ├── docx_worker.py
│       ├── xlsx_worker.py
│       └── chart_worker.py
├── data/
│   ├── chroma/
│   │   ├── docs_index/
│   │   ├── behavior_index/
│   │   └── execution_index/
│   ├── checkpoints/
│   └── artifacts/
├── configs/
│   ├── graph.yaml
│   ├── memory.yaml
│   └── models.yaml (migrate from agents/config.py)
└── tests/
    ├── test_graph_execution.py
    ├── test_memory_promotion.py
    ├── test_verifier_coverage.py
    └── test_ui_streaming.py
```

---

## Non-Negotiable Rules (Enforced in Code)

1. **Local GPU = embeddings only**
   - `services/memory/embedder.py` uses Ollama
   - Reasoning models via LiteLLM proxy only

2. **No answer before verification**
   - Graph edge: `verifier → composer` only if `state["verification_status"] == "PASSED"`

3. **Artifacts from structured state**
   - `services/workers/*` accept typed objects, not raw text

4. **Behavioral memory retrieved first**
   - Graph order: `intent_router → memory_prefetch → planner`

5. **Inline UI default**
   - All JSX elements use `display="inline"` prop

---

## Success Criteria

After Day 23:
- [ ] Graph executes chat/research/coding/artifact requests
- [ ] Behavioral memory injected before planning
- [ ] Verifier blocks unsupported claims
- [ ] Inline UI elements render in message flow
- [ ] Checkpointing allows resume after interruption
- [ ] LiteLLM fallback works on provider failure
- [ ] All tests pass

---

## Next Steps

Reply with:
1. **"Start Phase 1"** → I'll generate Day 1 starter code
2. **"Show me state.py first"** → I'll write the AgentState schema
3. **"Explain graph.py structure"** → I'll detail the 8-node graph
4. **"Generate all Phase 1 files"** → I'll create Days 1-6 code at once
