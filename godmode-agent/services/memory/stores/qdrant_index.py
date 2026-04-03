from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import os

class QdrantIndex:
    """
    Standardized Qdrant store for multiple indexes.
    Used for docs_index, behavior_index, and execution_index.
    """
    def __init__(self, collection_name: str, host: str = "localhost", port: int = 6333):
        # We can use a local file-based Qdrant or a running service
        # For this local-first approach, we default to local storage
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name

    def create_collection(self, vector_size: int = 768):
        """Initializes the collection with the correct vector size (for nomic-embed)."""
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def upsert(self, ids: List[int], vectors: List[List[float]], payloads: List[Dict]):
        """Upserts vectors and payloads into the collection."""
        self.client.upsert(
            collection_name=self.collection_name,
            points=models.Batch(
                ids=ids,
                vectors=vectors,
                payloads=payloads
            )
        )

    def search(self, vector: List[float], limit: int = 5) -> List[Dict]:
        """Searches for similar vectors and returns payloads."""
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit
        )
        return [hit.payload for hit in hits]

def init_collections():
    """Script to initialize the 3 required collections."""
    client = QdrantClient(host="localhost", port=6333)
    collections = ["docs_index", "behavior_index", "execution_index"]
    
    for coll in collections:
        print(f"Initializing collection: {coll}...")
        client.recreate_collection(
            collection_name=coll,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
    print("All collections initialized.")

if __name__ == "__main__":
    init_collections()
