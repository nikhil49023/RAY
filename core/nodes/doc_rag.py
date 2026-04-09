from core.state import AgentState

def doc_rag(state: AgentState) -> dict:
    """
    Retrieves information from document memory (PDFs, notes, codebase).
    In Phase 2, this will hit chroma_or_qdrant/docs_index.
    """
    intent = state.get("intent", "chat")
    plan = state.get("plan", "")
    
    # Mock retrieval for Phase 1
    # Check if doc retrieval is needed
    if "doc" in plan.lower() or intent == "research":
        evidence = [
            {"source": "docs", "claim": "Found system architecture details in docs-index (Mocked).", "confidence": 0.85}
        ]
    else:
        evidence = []
        
    return {
        "evidence": evidence,
        "current_task": "Document RAG Complete"
    }
