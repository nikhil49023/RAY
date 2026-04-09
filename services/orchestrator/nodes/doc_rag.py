from pathlib import Path
import sys
import importlib.util

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings
from services.orchestrator.state import AgentState


def doc_rag(state: AgentState) -> AgentState:
    """Retrieve documents from local RAG collection."""
    state["retrieval_attempts"] = state.get("retrieval_attempts", 0) + 1

    # Check if RAG is available
    if importlib.util.find_spec("chromadb") is None:
        state["doc_rag_results"] = []
        return state

    try:
        chromadb = importlib.import_module("chromadb")

        # Try remote first
        try:
            client = chromadb.HttpClient(
                host=settings.rag_chroma_host, port=settings.rag_chroma_port
            )
            client.heartbeat()
        except Exception:
            # Fallback to local
            local_path = Path(settings.rag_chroma_local_path)
            if not local_path.is_absolute():
                local_path = ROOT_DIR / local_path
            client = chromadb.PersistentClient(path=str(local_path))

        # Get collection
        collection = client.get_collection(name=settings.rag_collection_name)

        # Query
        results = collection.query(
            query_texts=[state["user_query"]], n_results=settings.rag_top_k
        )

        # Format results
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        formatted = []
        for i, doc in enumerate(docs):
            formatted.append(
                {
                    "content": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else 1.0,
                    "source": "local_rag",
                }
            )

        state["doc_rag_results"] = formatted

    except Exception as e:
        state["doc_rag_results"] = []
        if not state.get("error"):
            state["error"] = f"RAG error: {str(e)}"

    return state
