from pathlib import Path
import sys
import importlib.util
import json
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings


class ExecutionIndex:
    """Store for previous plans, workflows, and artifact metadata."""
    
    def __init__(self):
        self.collection_name = "ray_execution"
        self.client = None
        self.fallback_file = ROOT_DIR / "data" / "memory" / "execution_history.jsonl"
        self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_client()
    
    def _init_client(self):
        if importlib.util.find_spec("chromadb") is None:
            return
        
        chromadb = importlib.import_module("chromadb")
        
        try:
            self.client = chromadb.HttpClient(
                host=settings.rag_chroma_host,
                port=settings.rag_chroma_port
            )
            self.client.heartbeat()
        except Exception:
            local_path = Path(settings.rag_chroma_local_path)
            if not local_path.is_absolute():
                local_path = ROOT_DIR / local_path
            self.client = chromadb.PersistentClient(path=str(local_path))
    
    def add_execution(self, query: str, plan: dict, result: dict):
        """Store execution record."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "plan": plan,
            "result": result
        }
        
        # Fallback to JSONL
        with self.fallback_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
        
        # TODO: Add to Chroma collection if available
    
    def query_similar_plans(self, query_text: str, top_k: int = 3):
        """Find similar previous executions."""
        # For now, return empty - implement Chroma query later
        return []
