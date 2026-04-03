from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.behavioral_memory import BehavioralMemory
from agents.config import settings
from services.orchestrator.state import AgentState


def memory_writeback(state: AgentState) -> AgentState:
    """Extract and persist behavioral preferences from interaction."""
    
    if not settings.behavior_memory_enabled:
        return state
    
    memory = BehavioralMemory()
    
    # Extract preferences from user query
    captured = memory.capture_feedback(
        state["user_query"],
        source="langgraph_interaction"
    )
    
    # Also extract from final answer if it contains user corrections
    if state.get("final_answer"):
        answer_lower = state["final_answer"].lower()
        correction_signals = ["actually", "correction", "instead", "not quite", "wrong"]
        
        if any(signal in answer_lower for signal in correction_signals):
            memory.capture_feedback(
                state["final_answer"],
                source="langgraph_correction"
            )
    
    return state
