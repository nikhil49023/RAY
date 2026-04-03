from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.behavioral_memory import BehavioralMemory
from agents.config import settings
from services.orchestrator.state import AgentState


def memory_prefetch(state: AgentState) -> AgentState:
    """Retrieve behavioral rules before planning."""
    if not settings.behavior_memory_enabled:
        state["behavioral_rules"] = []
        state["applied_rules"] = []
        return state
    
    memory = BehavioralMemory()
    query = state["user_query"]
    
    # Retrieve top-k behavioral rules
    rules = memory.retrieve(query, top_k=settings.behavior_memory_top_k)
    
    state["behavioral_rules"] = rules
    state["applied_rules"] = rules  # Track which rules were actually used
    
    return state
