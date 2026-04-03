import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.orchestrator.nodes.verifier import verifier
from services.orchestrator.state import AgentState


def test_research_requires_evidence():
    """Test that research intent requires evidence."""
    
    state: AgentState = {
        "user_query": "Research LangGraph benefits",
        "session_id": "test",
        "intent": "research",
        "behavioral_rules": [],
        "applied_rules": [],
        "plan": {},
        "subtasks": [],
        "doc_rag_results": [],  # No evidence
        "web_rag_results": [],  # No evidence
        "code_results": [],
        "evidence": [],
        "verification_status": "PENDING",
        "verification_reason": "",
        "final_answer": "",
        "artifact_path": "",
        "model_name": "test",
        "checkpoint_mode": "async",
        "error": ""
    }
    
    result = verifier(state)
    
    assert result["verification_status"] == "FAILED"
    assert "evidence" in result["verification_reason"].lower()
    
    print("✓ Research evidence requirement test passed")


def test_chat_allows_no_evidence():
    """Test that chat intent allows no evidence."""
    
    state: AgentState = {
        "user_query": "Hello, how are you?",
        "session_id": "test",
        "intent": "chat",
        "behavioral_rules": [],
        "applied_rules": [],
        "plan": {},
        "subtasks": [],
        "doc_rag_results": [],
        "web_rag_results": [],
        "code_results": [],
        "evidence": [],
        "verification_status": "PENDING",
        "verification_reason": "",
        "final_answer": "",
        "artifact_path": "",
        "model_name": "test",
        "checkpoint_mode": "async",
        "error": ""
    }
    
    result = verifier(state)
    
    assert result["verification_status"] == "PASSED"
    
    print("✓ Chat no-evidence test passed")


def test_factual_query_requires_evidence():
    """Test that factual queries require evidence."""
    
    state: AgentState = {
        "user_query": "What is LangGraph?",
        "session_id": "test",
        "intent": "chat",
        "behavioral_rules": [],
        "applied_rules": [],
        "plan": {},
        "subtasks": [],
        "doc_rag_results": [],
        "web_rag_results": [],
        "code_results": [],
        "evidence": [],
        "verification_status": "PENDING",
        "verification_reason": "",
        "final_answer": "",
        "artifact_path": "",
        "model_name": "test",
        "checkpoint_mode": "async",
        "error": ""
    }
    
    result = verifier(state)
    
    assert result["verification_status"] == "FAILED"
    assert "evidence" in result["verification_reason"].lower()
    
    print("✓ Factual query evidence requirement test passed")


def test_passes_with_evidence():
    """Test that verification passes with sufficient evidence."""
    
    state: AgentState = {
        "user_query": "What is LangGraph?",
        "session_id": "test",
        "intent": "research",
        "behavioral_rules": [],
        "applied_rules": [],
        "plan": {},
        "subtasks": [],
        "doc_rag_results": [
            {"content": "LangGraph is a framework", "source": "docs", "distance": 0.2}
        ],
        "web_rag_results": [],
        "code_results": [],
        "evidence": [],
        "verification_status": "PENDING",
        "verification_reason": "",
        "final_answer": "",
        "artifact_path": "",
        "model_name": "test",
        "checkpoint_mode": "async",
        "error": ""
    }
    
    result = verifier(state)
    
    assert result["verification_status"] == "PASSED"
    assert len(result["evidence"]) > 0
    
    print("✓ Evidence coverage test passed")


if __name__ == "__main__":
    print("Running verifier tests...\n")
    
    try:
        test_research_requires_evidence()
        test_chat_allows_no_evidence()
        test_factual_query_requires_evidence()
        test_passes_with_evidence()
        
        print("\n✅ All verifier tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
