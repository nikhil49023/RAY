from services.orchestrator.state import AgentState
from services.memory.ollama_embedder import embedder
from services.memory.stores.qdrant_index import QdrantIndex

# Initialize the behavior index store
behavior_index = QdrantIndex(collection_name="behavior_index")

def memory_prefetch(state: AgentState) -> dict:
    """
    Retrieves behavioral rules and user preferences from Qdrant.
    Directly calls Ollama for embeddings to respect VRAM constraints.
    """
    user_input = state["messages"][-1].content
    
    # Generate embedding for the query
    try:
        query_vector = embedder.embed_query(user_input)
        
        # Search for behavioral rules
        hits = behavior_index.search(vector=query_vector, limit=5)
        
        # Extract rules from payloads
        behavioral_memories = [hit.get("rule") for hit in hits if "rule" in hit]
        
    except Exception as e:
        print(f"Memory prefetch warning: {e}")
        behavioral_memories = []
    
    # Fallback/Default rules if none found
    if not behavioral_memories:
        behavioral_memories = [
            "Rule: Prefer concise, high-confidence explanations.",
            "Rule: Always cite sources from doc_rag or web_rag."
        ]
    
    return {
        "behavioral_memories": behavioral_memories,
        "current_task": "Behavioral Memory Prefetched (Qdrant)"
    }
