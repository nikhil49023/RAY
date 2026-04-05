"""
graph.py — LangGraph Pipeline
-------------------------------
Smart pipeline with conditional routing:
  summarizer → memory_prefetch → intent_router → planner → [web_rag → deep_research] or [skip] → composer → memory_writeback → END

Reasoning mode skips all web nodes for pure AI thinking.
"""

from langgraph.graph import StateGraph, END
from services.orchestrator.state import AgentState

from services.orchestrator.nodes.summarizer import summarizer
from services.orchestrator.nodes.memory_prefetch import memory_prefetch
from services.orchestrator.nodes.intent_router import intent_router
from services.orchestrator.nodes.planner import planner
from services.orchestrator.nodes.web_rag import web_rag
from services.orchestrator.nodes.deep_research_rag import deep_research_rag
from services.orchestrator.nodes.composer import composer
from services.orchestrator.nodes.memory_writeback import memory_writeback


def _route_after_planner(state: dict) -> str:
    """Skip web search nodes entirely for memory recall or reasoning mode."""
    if state.get("intent") == "memory_recall":
        return "composer"
    research_level = state.get("research_level", "basic")
    if research_level == "none":
        return "composer"
    return "web_rag"


def create_graph():
    g = StateGraph(AgentState)

    # Nodes
    g.add_node("summarizer", summarizer)
    g.add_node("memory_prefetch", memory_prefetch)
    g.add_node("intent_router", intent_router)
    g.add_node("planner", planner)
    g.add_node("web_rag", web_rag)
    g.add_node("deep_research", deep_research_rag)
    g.add_node("composer", composer)
    g.add_node("memory_writeback", memory_writeback)

    # Flow with conditional routing
    g.set_entry_point("summarizer")
    g.add_edge("summarizer", "memory_prefetch")
    g.add_edge("memory_prefetch", "intent_router")
    g.add_edge("intent_router", "planner")

    # Planner decides: skip web for reasoning, or proceed
    g.add_conditional_edges("planner", _route_after_planner, {
        "web_rag": "web_rag",
        "composer": "composer",
    })

    g.add_edge("web_rag", "deep_research")
    g.add_edge("deep_research", "composer")
    g.add_edge("composer", "memory_writeback")
    g.add_edge("memory_writeback", END)

    return g.compile()


graph = create_graph()
