from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.memory.stores.docs_index import DocsIndex
from services.memory.stores.behavior_index import BehaviorIndex
from services.memory.stores.execution_index import ExecutionIndex


class MemoryRetriever:
    """Mem0-style multi-layer memory retrieval."""
    
    def __init__(self):
        self.docs = DocsIndex()
        self.behavior = BehaviorIndex()
        self.execution = ExecutionIndex()
    
    def retrieve_all(self, query: str, top_k: int = 5):
        """Retrieve from all memory layers with user memory ranked first."""
        
        # Layer 1: Behavioral rules (user memory) - highest priority
        behavioral_rules = self.behavior.query(query, top_k=top_k)
        
        # Layer 2: Document memory
        doc_results = self.docs.query(query, top_k=top_k)
        
        # Layer 3: Execution memory (session memory)
        execution_results = self.execution.query_similar_plans(query, top_k=3)
        
        return {
            "behavioral_rules": behavioral_rules,
            "documents": doc_results,
            "executions": execution_results
        }
    
    def retrieve_behavioral_only(self, query: str, top_k: int = 4):
        """Retrieve only behavioral rules for pre-prompt injection."""
        return self.behavior.query(query, top_k=top_k)
