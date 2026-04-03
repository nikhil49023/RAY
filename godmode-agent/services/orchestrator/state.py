"""
state.py — God Mode Agent State Schema
---------------------------------------
Single source of truth for all data flowing through the LangGraph pipeline.
Every node reads from and writes to this TypedDict.
"""

from typing import Annotated, Dict, List, TypedDict, Optional, Literal
from langchain_core.messages import BaseMessage
import operator


def merge_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    return left + right


class AgentState(TypedDict, total=False):
    # ── Core ─────────────────────────────────────────────────────────────── #
    messages: Annotated[List[BaseMessage], merge_messages]

    # ── Context Pipeline ─────────────────────────────────────────────────── #
    session_summary: Optional[str]
    recent_messages: List[BaseMessage]
    turn_count: int

    # ── Routing & Planning ───────────────────────────────────────────────── #
    intent: Optional[str]
    research_level: Optional[Literal["none", "basic", "deep"]]
    rewritten_query: Optional[str]
    plan: Optional[str]
    temperature: Optional[float]

    # ── Evidence (merged via operator.add across parallel nodes) ──────────── #
    evidence: Annotated[List[dict], operator.add]
    thinking_log: Annotated[List[dict], operator.add]

    # ── Output ───────────────────────────────────────────────────────────── #
    answer: Optional[str]
    artifacts: List[dict]
    current_task: Optional[str]
    completed_nodes: List[str]
    node_timings: Dict[str, float]

    # ── User Controls ────────────────────────────────────────────────────── #
    agent_mode: str
    selected_model: str

    # ── Error Tracking ───────────────────────────────────────────────────── #
    errors: List[str]
