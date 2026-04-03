from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from services.orchestrator.state import AgentState
from services.orchestrator.nodes.intent_router import intent_router
from services.orchestrator.nodes.memory_prefetch import memory_prefetch
from services.orchestrator.nodes.planner import planner
from services.orchestrator.nodes.doc_rag import doc_rag
from services.orchestrator.nodes.web_rag import web_rag
from services.orchestrator.nodes.verifier import verifier
from services.orchestrator.nodes.composer import composer
from services.orchestrator.nodes.memory_writeback import memory_writeback


def should_retry_retrieval(state: AgentState) -> str:
    """Route back to retrieval if verification fails."""
    if state.get("verification_status") == "FAILED":
        return "doc_rag"
    return "composer"


def build_graph(checkpoint_path: str = "data/checkpoints/graph.db") -> StateGraph:
    """Build the LangGraph state machine."""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("intent_router", intent_router)
    workflow.add_node("memory_prefetch", memory_prefetch)
    workflow.add_node("planner", planner)
    workflow.add_node("doc_rag", doc_rag)
    workflow.add_node("web_rag", web_rag)
    workflow.add_node("verifier", verifier)
    workflow.add_node("composer", composer)
    workflow.add_node("memory_writeback", memory_writeback)
    
    # Define edges
    workflow.set_entry_point("intent_router")
    workflow.add_edge("intent_router", "memory_prefetch")
    workflow.add_edge("memory_prefetch", "planner")
    workflow.add_edge("planner", "doc_rag")
    workflow.add_edge("planner", "web_rag")
    workflow.add_edge("doc_rag", "verifier")
    workflow.add_edge("web_rag", "verifier")
    
    # Conditional edge: retry retrieval if verification fails
    workflow.add_conditional_edges(
        "verifier",
        should_retry_retrieval,
        {
            "doc_rag": "doc_rag",
            "composer": "composer",
        }
    )
    
    workflow.add_edge("composer", "memory_writeback")
    workflow.add_edge("memory_writeback", END)
    
    # Compile with checkpointing
    checkpointer = SqliteSaver.from_conn_string(checkpoint_path)
    return workflow.compile(checkpointer=checkpointer)
