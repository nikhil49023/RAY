from services.orchestrator.state import AgentState
from services.memory.semantic_memory import retrieve_semantic_memory

def memory_prefetch(state: AgentState) -> dict:
    """
    Retrieve semantic memory and behavioral preferences before planning.
    """
    if state.get("memory_context") or state.get("behavioral_memories"):
        return {
            "memory_context": state.get("memory_context", ""),
            "memory_hits": state.get("memory_hits", []),
            "behavioral_memories": state.get("behavioral_memories", []),
            "current_task": "Memory context already available",
        }

    user_input = state["messages"][-1].content
    top_k = 10 if state.get("agent_mode") == "research" else 5
    retrieved = retrieve_semantic_memory(str(user_input), top_k=top_k)

    return {
        "behavioral_memories": retrieved.get("behavioral_memories", []),
        "memory_hits": retrieved.get("memory_hits", []),
        "memory_context": retrieved.get("memory_context", ""),
        "current_task": "Semantic memory prefetched",
    }
