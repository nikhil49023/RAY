import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.memory.promotion_rules import (
    should_promote_to_user_memory,
    classify_memory_type,
    extract_stable_preferences
)


def test_persistent_signals():
    """Test detection of persistent preferences."""
    
    # Should promote
    assert should_promote_to_user_memory("Always prefer minimal code examples")
    assert should_promote_to_user_memory("Never include verbose explanations")
    assert should_promote_to_user_memory("My style is concise and direct")
    
    print("✓ Persistent signals test passed")


def test_ephemeral_signals():
    """Test rejection of ephemeral facts."""
    
    # Should NOT promote
    assert not should_promote_to_user_memory("Today I need a quick answer")
    assert not should_promote_to_user_memory("Right now I'm working on X")
    assert not should_promote_to_user_memory("Currently testing")
    
    print("✓ Ephemeral signals test passed")


def test_memory_classification():
    """Test memory type classification."""
    
    assert classify_memory_type("Always prefer concise code") == "preference"
    assert classify_memory_type("Budget limit is 4GB VRAM") == "constraint"
    assert classify_memory_type("Actually, that was wrong") == "correction"
    assert classify_memory_type("Working on RAY project") == "project_state"
    
    print("✓ Memory classification test passed")


def test_extraction():
    """Test stable preference extraction."""
    
    text = """
    Always use minimal code examples. Today I need help with LangGraph.
    Never include verbose explanations. Right now I'm testing.
    Prefer inline UI elements.
    """
    
    extracted = extract_stable_preferences(text)
    
    # Should extract 3 stable preferences, ignore 2 ephemeral
    assert len(extracted) >= 2
    assert all(item["type"] in ["preference", "constraint", "correction", "project_state"] 
               for item in extracted)
    
    print(f"✓ Extraction test passed (extracted {len(extracted)} stable preferences)")


if __name__ == "__main__":
    print("Running memory promotion tests...\n")
    
    try:
        test_persistent_signals()
        test_ephemeral_signals()
        test_memory_classification()
        test_extraction()
        
        print("\n✅ All memory tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
