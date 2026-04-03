from services.orchestrator.state import AgentState


def intent_router(state: AgentState) -> AgentState:
    """Classify user query into intent categories."""
    query = state["user_query"].lower()
    
    # Research intent: long-running, needs sync checkpointing
    if any(kw in query for kw in ["research", "analyze", "investigate", "deep dive", "comprehensive"]):
        state["intent"] = "research"
        state["checkpoint_mode"] = "sync"
    
    # Coding intent
    elif any(kw in query for kw in ["code", "implement", "function", "class", "debug", "refactor"]):
        state["intent"] = "coding"
        state["checkpoint_mode"] = "async"
    
    # Dashboard/visualization intent
    elif any(kw in query for kw in ["dashboard", "chart", "graph", "visualize", "plot"]):
        state["intent"] = "dashboard"
        state["checkpoint_mode"] = "async"
    
    # Artifact generation intent
    elif any(kw in query for kw in ["generate", "create pdf", "create docx", "export", "download"]):
        state["intent"] = "artifact"
        state["checkpoint_mode"] = "sync"
    
    # Default: chat intent
    else:
        state["intent"] = "chat"
        state["checkpoint_mode"] = "async"
    
    return state
