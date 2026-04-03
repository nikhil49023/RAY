# RAY God Mode Agent: System Architecture

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Chainlit UI                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ScoreCard │  │Evidence  │  │Timeline  │  │Dashboard │       │
│  │          │  │Table     │  │          │  │Panel     │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph Orchestrator                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    State Machine                         │   │
│  │                                                           │   │
│  │  [Intent Router] → [Memory Prefetch] → [Planner]       │   │
│  │         ↓                                    ↓           │   │
│  │         ↓              ┌──────────────┐     ↓           │   │
│  │         ↓              │  Doc RAG     │ ←───┘           │   │
│  │         ↓              └──────────────┘                 │   │
│  │         ↓              ┌──────────────┐                 │   │
│  │         ↓              │  Web RAG     │                 │   │
│  │         ↓              └──────────────┘                 │   │
│  │         ↓                      ↓                         │   │
│  │         ↓              [Verifier] ←──────┐              │   │
│  │         ↓                      ↓          │              │   │
│  │         ↓              PASSED? ─── NO ────┘              │   │
│  │         ↓                      │                         │   │
│  │         ↓                     YES                        │   │
│  │         ↓                      ↓                         │   │
│  │         ↓              [Composer]                        │   │
│  │         ↓                      ↓                         │   │
│  │         └──────────→ [Memory Writeback]                 │   │
│  │                                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Checkpoint: SQLite (data/checkpoints/graph.db)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Memory System (Mem0)                        │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Docs Index   │  │Behavior Index│  │Execution Idx │         │
│  │              │  │              │  │              │         │
│  │ ray_docs     │  │ ray_behavior │  │ ray_execution│         │
│  │              │  │              │  │              │         │
│  │ Priority: 2  │  │ Priority: 1  │  │ Priority: 3  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                   │
│  Embeddings: Ollama (nomic-embed-text)                          │
│  Storage: ChromaDB (local + remote)                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  LiteLLM     │  │  Firecrawl   │  │  Ollama      │         │
│  │  Router      │  │  Scraper     │  │  Embeddings  │         │
│  │              │  │              │  │              │         │
│  │ :4000        │  │ :3002        │  │ :11434       │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                   │
│  Fallback Chain: premium-thinker → llama-3.3-70b →             │
│                  openrouter/free → deepseek-r1:8b               │
└─────────────────────────────────────────────────────────────────┘
```

## Node Execution Detail

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Intent Router                                                 │
│    Input:  user_query                                            │
│    Output: intent (chat|research|coding|dashboard|artifact)     │
│            checkpoint_mode (sync|async)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Memory Prefetch                                               │
│    Input:  user_query                                            │
│    Action: Query behavior_index for top-4 rules                 │
│    Output: behavioral_rules, applied_rules                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Planner                                                       │
│    Input:  user_query, intent, behavioral_rules                 │
│    Action: LLM generates structured plan                        │
│    Output: plan, subtasks                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Doc RAG (parallel)                                            │
│    Input:  user_query                                            │
│    Action: Query docs_index (ray_docs collection)               │
│    Output: doc_rag_results                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Web RAG (parallel)                                            │
│    Input:  user_query                                            │
│    Action: Extract URLs, scrape via Firecrawl                   │
│    Output: web_rag_results                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. Verifier                                                      │
│    Input:  doc_rag_results, web_rag_results, intent             │
│    Action: Build evidence objects, check coverage               │
│    Output: evidence[], verification_status (PASSED|FAILED)     │
│                                                                   │
│    Rules:                                                        │
│    - research intent: requires ≥2 evidence                      │
│    - artifact intent: requires ≥1 evidence                      │
│    - factual query: requires ≥1 evidence                        │
│    - chat intent: no requirement                                │
│                                                                   │
│    If FAILED: loop back to doc_rag                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Composer                                                      │
│    Input:  evidence, behavioral_rules, user_query               │
│    Action: LLM generates answer ONLY from evidence              │
│    Output: final_answer                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. Memory Writeback                                              │
│    Input:  user_query, final_answer                             │
│    Action: Extract preferences, apply promotion rules           │
│    Output: (persists to behavior_index)                         │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Promotion Flow

```
User Query / Answer
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Extract Preferences                                              │
│                                                                   │
│ Signals:                                                         │
│ ✓ "always", "never", "prefer", "avoid"                          │
│ ✓ "my style", "for me", "from now on"                           │
│ ✗ "today", "right now", "currently"                             │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Classify Memory Type                                             │
│                                                                   │
│ - Preference: tone, formatting, UI, explanation                 │
│ - Constraint: budget, privacy, hardware, latency                │
│ - Correction: mistakes to avoid                                 │
│ - Project State: active repo, objective                         │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Promotion Decision                                               │
│                                                                   │
│ Promote to user_memory if:                                      │
│ ✓ Length ≥ 15 chars                                             │
│ ✓ Contains persistent signals                                   │
│ ✓ No ephemeral signals                                          │
│                                                                   │
│ Otherwise: discard or store in session_memory                   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Persist to Chroma                                                │
│                                                                   │
│ Collection: ray_behavior                                         │
│ Embedding: Ollama (nomic-embed-text)                            │
│ Fallback: JSONL (data/memory/behavior_rules.jsonl)             │
└─────────────────────────────────────────────────────────────────┘
```

## Artifact Generation Flow

```
Intent: artifact
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Planner determines artifact type                                 │
│ - PDF: report, document                                          │
│ - DOCX: editable document                                        │
│ - XLSX/CSV: data export                                          │
│ - HTML: chart, dashboard                                         │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Composer generates structured content                            │
│ Output: typed object (not raw text)                             │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Worker processes structured content                              │
│                                                                   │
│ PDFWorker:   content → ReportLab → .pdf                         │
│ DOCXWorker:  content → python-docx → .docx                      │
│ XLSXWorker:  data → csv → .csv                                  │
│ ChartWorker: data → Chart.js → .html                            │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Save to data/artifacts/                                          │
│ Return: artifact_path                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Reliability Mechanisms

```
┌─────────────────────────────────────────────────────────────────┐
│ Retry Policy                                                     │
│                                                                   │
│ Max retries: 3                                                   │
│ Backoff: exponential (2^attempt seconds)                        │
│                                                                   │
│ Retryable errors:                                                │
│ - timeout                                                        │
│ - rate limit (429)                                               │
│ - connection error                                               │
│ - service unavailable (503)                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Fallback Policy                                                  │
│                                                                   │
│ Model chain:                                                     │
│ 1. premium-thinker (LiteLLM alias)                              │
│ 2. llama-3.3-70b-versatile (Groq)                               │
│ 3. openrouter/free (OpenRouter)                                 │
│ 4. deepseek-r1:8b (Ollama local)                                │
│                                                                   │
│ Automatic failover on:                                           │
│ - Rate limit                                                     │
│ - Timeout                                                        │
│ - Model unavailable                                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Checkpointing                                                    │
│                                                                   │
│ Sync mode (research, artifact):                                 │
│ - Write to SQLite after each node                               │
│ - Resume from last checkpoint on failure                        │
│                                                                   │
│ Async mode (chat, coding, dashboard):                           │
│ - Buffer in memory                                               │
│ - Write on completion                                            │
│ - Faster execution                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Hardware Allocation

```
┌─────────────────────────────────────────────────────────────────┐
│ 4GB VRAM Budget                                                  │
│                                                                   │
│ Ollama (local):                                                  │
│ - nomic-embed-text: ~500MB                                      │
│ - deepseek-r1:8b (fallback): ~3.5GB                             │
│                                                                   │
│ Reserved for:                                                    │
│ ✓ Embeddings (docs, behavior, execution)                        │
│ ✓ Memory extraction                                              │
│ ✓ Retrieval helpers                                              │
│                                                                   │
│ NOT used for:                                                    │
│ ✗ Main reasoning (via LiteLLM → free providers)                │
│ ✗ Heavy inference                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
User Query
    ↓
[Intent + Memory] → Behavioral rules injected
    ↓
[Planner] → Structured plan with subtasks
    ↓
[RAG Parallel] → Evidence collection
    ↓
[Verifier] → Coverage check (retry if failed)
    ↓
[Composer] → Evidence-only answer
    ↓
[Memory Writeback] → Extract + persist preferences
    ↓
[UI Render] → Inline elements + final answer
```

## Key Metrics

- **Nodes**: 8
- **Collections**: 3 (docs, behavior, execution)
- **UI Elements**: 5 (ScoreCard, EvidenceTable, Timeline, Dashboard, Badge)
- **Workers**: 4 (PDF, DOCX, XLSX, Chart)
- **Tests**: 3 suites (graph, memory, verifier)
- **Fallback Models**: 4
- **Max Retries**: 3
- **Checkpoint Modes**: 2 (sync, async)
