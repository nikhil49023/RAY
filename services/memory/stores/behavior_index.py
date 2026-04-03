from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.behavioral_memory import BehavioralMemory


class BehaviorIndex:
    """Wrapper for behavioral memory collection."""
    
    def __init__(self):
        self.memory = BehavioralMemory()
    
    def query(self, query_text: str, top_k: int = 4):
        """Retrieve behavioral rules."""
        return self.memory.retrieve(query_text, top_k=top_k)
    
    def add(self, rule: str, source: str = "manual"):
        """Add behavioral rule."""
        return self.memory.capture_feedback(rule, source=source)
    
    def status(self):
        """Check memory status."""
        return self.memory.status()
