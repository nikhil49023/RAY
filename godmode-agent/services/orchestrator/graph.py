"""
graph.py — LangGraph Pipeline
-------------------------------
Smart pipeline with conditional routing:
  intent_router → planner → [web_rag → deep_research] or [skip] → composer → END

Reasoning mode skips all web nodes for pure AI thinking.
"""

from langgraph.graph import StateGraph, END
from services.orchestrator.state import AgentState

from services.orchestrator.nodes.intent_router import intent_router
from services.orchestrator.nodes.planner import planner
from services.orchestrator.nodes.web_rag import web_rag
from services.orchestrator.nodes.deep_research_rag import deep_research_rag
from services.orchestrator.nodes.composer import composer


def _route_after_planner(state: dict) -> str:
    """Skip web search nodes entirely for reasoning mode."""
    research_level = state.get("research_level", "basic")
    if research_level == "none":
        return "composer"
    return "web_rag"


def create_graph():
    g = StateGraph(AgentState)

    # Nodes
    g.add_node("intent_router", intent_router)
    g.add_node("planner", planner)
    g.add_node("web_rag", web_rag)
    g.add_node("deep_research", deep_research_rag)
    g.add_node("composer", composer)

    # Flow with conditional routing
    g.set_entry_point("intent_router")
    g.add_edge("intent_router", "planner")

    # Planner decides: skip web for reasoning, or proceed
    g.add_conditional_edges("planner", _route_after_planner, {
        "web_rag": "web_rag",
        "composer": "composer",
    })

    g.add_edge("web_rag", "deep_research")
    g.add_edge("deep_research", "composer")
    g.add_edge("composer", END)

    return g.compile()


graph = create_graph()
