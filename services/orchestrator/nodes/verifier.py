from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.orchestrator.state import AgentState, Evidence


def verifier(state: AgentState) -> AgentState:
    """Validate evidence coverage before allowing final answer."""
    
    doc_results = state.get("doc_rag_results", [])
    web_results = state.get("web_rag_results", [])
    
    # Build evidence objects
    evidence = []
    
    for doc in doc_results:
        evidence.append(Evidence(
            claim=doc.get("content", "")[:200],
            source=doc.get("source", "local_rag"),
            confidence=1.0 - doc.get("distance", 0.5),
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    
    for web in web_results:
        evidence.append(Evidence(
            claim=web.get("content", "")[:200],
            source=web.get("url", "web"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    
    state["evidence"] = evidence
    
    # Verification rules
    intent = state.get("intent", "chat")
    
    # Research and artifact intents require evidence
    if intent in ["research", "artifact"]:
        if len(evidence) == 0:
            state["verification_status"] = "FAILED"
            state["verification_reason"] = "No evidence found for research/artifact request"
            return state
    
    # All intents: if query mentions specific facts, require at least 1 source
    query_lower = state["user_query"].lower()
    fact_keywords = ["what is", "how does", "explain", "define", "describe"]
    
    if any(kw in query_lower for kw in fact_keywords) and len(evidence) == 0:
        state["verification_status"] = "FAILED"
        state["verification_reason"] = "Factual query requires evidence"
        return state
    
    # Pass verification
    state["verification_status"] = "PASSED"
    state["verification_reason"] = f"Evidence coverage: {len(evidence)} sources"
    
    return state
