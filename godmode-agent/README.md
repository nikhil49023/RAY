# RAY God Mode Agent

> **A production-grade, glass-box AI assistant powered by LangGraph, Qdrant, Ollama, and LiteLLM.**

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange)](https://github.com/langchain-ai/langgraph)
[![Chainlit](https://img.shields.io/badge/Chainlit-UI-green)](https://chainlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           LangGraph StateMachine                        │
│                                                                         │
│  [summarizer] ──────────────► rolls session_summary every 6 turns       │
│       │                                                                 │
│       ▼                                                                 │
│  [intent_router] ─── query rewriting ──► rewritten_query                │
│       │                                                                 │
│       ▼                                                                 │
│  [memory_prefetch] ─── Qdrant behavioral index ──► applied_rules        │
│       │                                                                 │
│       ▼                                                                 │
│  [planner] ──────────────────────────────► structured plan              │
│       │                                                                 │
│       ├──────────────── parallel ────────────────┐                      │
│       ▼                                          ▼                      │
│  [doc_rag]                                  [web_rag]                   │
│  (Qdrant docs)                         (DuckDuckGo / SerpAPI)           │
│       │                                          │                      │
│       └──────────────── join ───────────────────-┘                      │
│                              │                                          │
│                              ▼                                          │
│                    [research_subagent] ── 500-token Research Brief       │
│                              │                                          │
│                              ▼                                          │
│                         [verifier] ── PASSED / FAILED ──► [planner]     │
│                              │                                          │
│                              ▼                                          │
│                         [composer] ──────────────► final answer         │
│                              │                                          │
│                              ▼                                          │
│                     [memory_writeback] ── Qdrant behavioral index        │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Chainlit UI
  ├── ResearchTimeline  (live node progress)
  ├── MemoryBadge       (applied behavioral rules)
  ├── DashboardPanel    (token budget, latency, confidence)
  └── EvidenceTable     (claim → source mapping)
```

### Context Engineering Layers

| Layer | Mechanism | Budget role |
|---|---|---|
| `session_summary` | Rolling 4-part summary (Goal/Decisions/Facts/Open) | Replaces old history |
| `recent_messages` | 6-message verbatim window | Preserves fresh context |
| `applied_rules`   | ≤5 behavioral rules from Qdrant | Injected into composer |
| `research_subagent` | Distils RAG output → ≤500-token brief | Prevents doc bloat |
| **Total budget** | **8 k–12 k tokens per call** | Enforced by composer |

---

## Setup

### Prerequisites

| Service | Purpose | Default Port |
|---|---|---|
| [Ollama](https://ollama.com/) | Local LLM + embeddings | `11434` |
| [Qdrant](https://qdrant.tech/) | Vector store (memory + docs) | `6333` |
| [LiteLLM](https://litellm.ai/) | LLM proxy / router | `4000` |

### Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/godmode-agent
cd godmode-agent

# 2. Environment
cp .env.example .env
# → Edit .env with your API keys

# 3. Install
pip install -r requirements.txt

# 4. Start infrastructure
ollama pull llama3          # local LLM
ollama pull nomic-embed-text # embeddings
docker run -p 6333:6333 qdrant/qdrant
litellm --config configs/litellm_config.yaml

# 5. Run UI
cd apps/ui-chainlit
chainlit run app.py --watch
```

---

## UI Components

### `ResearchTimeline`
Displays the live LangGraph node pipeline with animated progress, per-node
elapsed timings, and a pulsing active-node indicator.

**Props:** `{ status, activeNode, completedNodes, timings, error }`

### `MemoryBadge`
Collapsible badge list showing which behavioral rules were injected this turn,
colour-coded by priority tier (HIGH / MED / LOW).

**Props:** `{ rules: string[] }`

### `DashboardPanel`
Session telemetry panel: confidence ring, source count, animated token-budget
bar with colour-coded warning zones (yellow > 60%, red > 85%).

**Props:** `{ metrics: { confidence, sourceCount, tokenUsage, processingTime, factualCertainty, tokenBudget, summaryTurn } }`

### `EvidenceTable`
Interactive claim-to-source table. Click a row to expand the source excerpt.
Colour-coded provenance badge (web / document / memory).

**Props:** `{ evidence: [{ claim, source, url, type, confidence, excerpt? }] }`

---

## Context Pipeline Details

### Summarizer Node (`summarizer.py`)
- **Turn trigger:** every 6 turns (configurable via `SUMMARIZE_EVERY_N_TURNS`)
- **Token trigger:** when estimated history exceeds 4 000 tokens
- **Output format:** `Goal | Decisions | Facts | Open`
- **Window:** last 6 messages kept verbatim alongside the summary

### Query Rewriter (inside `intent_router.py`)
- Resolves pronouns and implicit references using `session_summary`
- Falls back gracefully to the raw query on LLM error

### Research Sub-Agent (`research_subagent.py`)
- Accepts raw doc_rag + web_rag results
- Distils to a `ResearchBrief` dataclass (≤500 tokens)
- Exposes `to_evidence_list()` for the EvidenceTable and `as_context_block()` for the composer

---

## Testing

```bash
# Context engineering tests
pytest tests/test_context_engineering.py -v

# Summarization unit tests
pytest tests/test_summarization.py -v

# All tests
pytest tests/ -v --tb=short
```

---

## Roadmap

- [ ] Multi-modal evidence (image captions in EvidenceTable)
- [ ] Pluggable summarizer backends (local Ollama models)
- [ ] Chainlit OAuth + per-user Qdrant namespaces
- [ ] Streaming token counter (real-time DashboardPanel updates)
- [ ] GitHub Actions CI for test suite

---

## License

MIT © RAY Project Contributors
