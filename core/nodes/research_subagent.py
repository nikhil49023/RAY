"""
research_subagent.py – Phase 5: Specialist Research Sub-Agent
-------------------------------------------------------------
Takes a focused query, performs multi-hop search (doc_rag → web_rag),
and distils results into a ≤500-token "Research Brief" — preventing
main-thread context bloat by returning structured summary rather than
raw retrieved documents.

Research Brief format:
    Summary     : <2-3 sentence answer>
    Key Facts   : <bullet list of ≤5 verified facts>
    Sources     : <list of {source, url, confidence}>
    Confidence  : <0.0–1.0 float>
    Gaps        : <what could not be answered / caveats>
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from core.llm_factory import LLMFactory
from core.state import AgentState

# ──────────────────────────────────────────────────────────────────────────── #
# Data model for the Research Brief                                            #
# ──────────────────────────────────────────────────────────────────────────── #

@dataclass
class ResearchBrief:
    query:      str
    summary:    str
    key_facts:  List[str]   = field(default_factory=list)
    sources:    List[dict]  = field(default_factory=list)
    confidence: float       = 0.0
    gaps:       str         = ""
    elapsed:    float       = 0.0

    def to_evidence_list(self) -> List[dict]:
        """Convert brief into the evidence[] schema expected by state.py."""
        return [
            {
                "claim":      fact,
                "source":     src.get("source", "research_subagent"),
                "url":        src.get("url", ""),
                "type":       "web",
                "confidence": self.confidence,
            }
            for fact, src in zip(
                self.key_facts,
                self.sources + [{}] * max(0, len(self.key_facts) - len(self.sources)),
            )
        ]

    def as_context_block(self) -> str:
        """Compact string injected into the composer's prompt (≤500 tokens)."""
        facts_str = "\n".join(f"  • {f}" for f in self.key_facts)
        srcs_str  = "\n".join(
            f"  [{i+1}] {s.get('source','?')} – {s.get('url','')}"
            for i, s in enumerate(self.sources[:5])
        )
        return (
            f"[Research Brief for: '{self.query}']\n"
            f"Summary    : {self.summary}\n"
            f"Key Facts  :\n{facts_str}\n"
            f"Sources    :\n{srcs_str}\n"
            f"Confidence : {self.confidence:.0%}\n"
            f"Gaps       : {self.gaps}"
        )


# ──────────────────────────────────────────────────────────────────────────── #
# LLM distiller logic                                                          #
# ──────────────────────────────────────────────────────────────────────────── #

_DISTIL_SYSTEM = """\
You are a Research Distiller for a God-Mode Agent.

You receive raw retrieved documents/snippets and must condense them into a
Research Brief in EXACTLY this format:

Summary    : <2-3 sentence direct answer>
Key Facts  :
  • <fact 1>
  • <fact 2>
  • <…up to 5>
Sources    :
  [1] <source name> – <url>
  [2] …
Confidence : <0.0–1.0>
Gaps       : <what remains unanswered or uncertain>

Be ruthlessly concise. Total output must fit within 500 tokens.
"""


def _parse_brief(query: str, raw: str, sources: List[dict], t0: float) -> ResearchBrief:
    """Parse the LLM distillation output into a ResearchBrief dataclass."""
    lines   = raw.splitlines()
    summary = ""
    facts   = []
    conf    = 0.0
    gaps    = ""
    in_facts = False

    for line in lines:
        ls = line.strip()
        if ls.startswith("Summary"):
            summary  = ls.split(":", 1)[-1].strip()
            in_facts = False
        elif ls.startswith("Key Facts"):
            in_facts = True
        elif in_facts and ls.startswith("•"):
            facts.append(ls.lstrip("• ").strip())
        elif ls.startswith("Confidence"):
            try:
                # Handle percentage or float
                val = ls.split(":", 1)[-1].strip().replace("%", "")
                conf = float(val) / 100.0 if "%" in ls else float(val)
            except ValueError:
                conf = 0.75
            in_facts = False
        elif ls.startswith("Gaps"):
            gaps     = ls.split(":", 1)[-1].strip()
            in_facts = False

    return ResearchBrief(
        query      = query,
        summary    = summary or raw[:200],
        key_facts  = facts,
        sources    = sources,
        confidence = conf or 0.75,
        gaps       = gaps,
        elapsed    = round(time.perf_counter() - t0, 3),
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Public API                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #

def run_research_subagent(
    query: str,
    raw_docs: Optional[List[dict]] = None,
    raw_web: Optional[List[dict]] = None,
    selected_model: str = "sarvam/sarvam-105b",
) -> ResearchBrief:
    """
    Standalone callable: distils raw retrieved content into a Research Brief.
    Now with regional routing (Sarvam-105B) for Indian context.
    """
    t0 = time.perf_counter()
    raw_docs = raw_docs or []
    raw_web  = raw_web or []
    all_docs = raw_docs + raw_web

    # Dynamic routing based on query complexity/context
    llm = LLMFactory.get_model(role="primary", temperature=0.1, max_tokens=700, model_id=selected_model)

    if not all_docs:
        return ResearchBrief(
            query      = query,
            summary    = "No source documents provided to Research Sub-Agent.",
            confidence = 0.0,
            gaps       = "No retrieval results available.",
            elapsed    = 0.0,
        )

    # Build compact document block (<2000 chars total to save tokens)
    doc_block = ""
    remaining = 2000
    sources   = []
    for doc in all_docs:
        snippet = doc.get("content", "")[:400]
        header  = f"[{doc.get('source','?')}] {doc.get('url','')}\n"
        chunk   = header + snippet + "\n\n"
        if len(chunk) > remaining:
            break
        doc_block += chunk
        remaining -= len(chunk)
        sources.append({"source": doc.get("source"), "url": doc.get("url")})

    try:
        response = llm.invoke([
            SystemMessage(content=_DISTIL_SYSTEM),
            HumanMessage(content=f"Query: {query}\n\nDocuments:\n{doc_block}"),
        ])
        return _parse_brief(query, response.content, sources, t0)
    except Exception as exc:
        print(f"[research_subagent] Error distilling brief: {exc}")
        return ResearchBrief(
            query      = query,
            summary    = f"Research sub-agent error: {exc}",
            confidence = 0.0,
            gaps       = "LLM distillation failed.",
            elapsed    = round(time.perf_counter() - t0, 3),
        )


# ──────────────────────────────────────────────────────────────────────────── #
# LangGraph node wrapper                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

def research_subagent(state: AgentState) -> dict:  # type: ignore[name-defined]
    """
    LangGraph node: wraps run_research_subagent for graph integration.
    """
    query    = state.get("rewritten_query") or state["messages"][-1].content
    raw_docs = [e for e in state.get("evidence", []) if e.get("type") == "document"]
    raw_web  = [e for e in state.get("evidence", []) if e.get("type") == "web"]

    selected_model = state.get("selected_model", "sarvam/sarvam-105b")
    brief    = run_research_subagent(query, raw_docs, raw_web, selected_model=selected_model)

    return {
        "evidence":     brief.to_evidence_list(),
        "current_task": "Research Brief Distilled",
        "node_timings": {**state.get("node_timings", {}), "research_subagent": brief.elapsed},
    }

