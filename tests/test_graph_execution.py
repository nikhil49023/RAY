import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.orchestrator.langgraph_orchestrator import LangGraphOrchestrator


def test_simple_chat():
    """Test basic chat execution."""
    orchestrator = LangGraphOrchestrator()
    
    result = orchestrator.run(
        query="What is LangGraph?",
        session_id="test_session_1"
    )
    
    assert result["status"] == "success"
    assert result["mode"] == "langgraph"
    assert len(result["answer"]) > 0
    print("✓ Simple chat test passed")


def test_research_intent():
    """Test research intent with evidence requirement."""
    orchestrator = LangGraphOrchestrator()
    
    result = orchestrator.run(
        query="Research the benefits of LangGraph for production agents",
        session_id="test_session_2"
    )
    
    assert result["status"] == "success"
    assert result["verification_status"] in ["PASSED", "FAILED"]
    print(f"✓ Research intent test passed (verification: {result['verification_status']})")


def test_behavioral_memory():
    """Test behavioral memory injection."""
    orchestrator = LangGraphOrchestrator()
    
    # First, add a preference
    from services.memory.stores.behavior_index import BehaviorIndex
    behavior = BehaviorIndex()
    behavior.add("Always prefer concise explanations", source="test")
    
    result = orchestrator.run(
        query="Explain LangGraph",
        session_id="test_session_3"
    )
    
    assert result["status"] == "success"
    print(f"✓ Behavioral memory test passed (applied {len(result['applied_rules'])} rules)")


def test_error_handling():
    """Test graceful error handling."""
    orchestrator = LangGraphOrchestrator()
    
    result = orchestrator.run(
        query="",  # Empty query
        session_id="test_session_4"
    )
    
    # Should handle gracefully
    assert result["mode"] == "langgraph"
    print("✓ Error handling test passed")


if __name__ == "__main__":
    print("Running LangGraph integration tests...\n")
    
    try:
        test_simple_chat()
        test_research_intent()
        test_behavioral_memory()
        test_error_handling()
        
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
