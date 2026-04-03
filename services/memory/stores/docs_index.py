from pathlib import Path
import sys
import importlib.util

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings


class DocsIndex:
    """Wrapper for existing RAG document collection."""
    
    def __init__(self):
        self.collection_name = settings.rag_collection_name
        self.client = None
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
    
    def query(self, query_text: str, top_k: int = 3):
        """Query document collection."""
        if not self.client:
            return []
        
        try:
            collection = self.client.get_collection(name=self.collection_name)
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k
            )
            
            docs = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            
            return [
                {"content": doc, "metadata": metadatas[i] if i < len(metadatas) else {}}
                for i, doc in enumerate(docs)
            ]
        except Exception:
            return []
