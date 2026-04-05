from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import os
import logging
import hashlib

logger = logging.getLogger("ray.qdrant")


class QdrantIndex:
    """
    Standardized Qdrant store for multiple indexes.
    Used for docs_index, behavior_index, and execution_index.
    Includes fallback for when Qdrant is unavailable.
    """

    def __init__(self, collection_name: str, host: str = "localhost", port: int = 6333):
        self.collection_name = collection_name
        self._client = None
        self._available = False
        self._vector_size = 512

        try:
            self._client = QdrantClient(host=host, port=port)
            self._client.get_collection(collection_name=collection_name)
            self._available = True
            logger.info(f"Connected to Qdrant collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Qdrant not available for {collection_name}: {e}")
            self._client = None
            self._available = False

    def create_collection(self, vector_size: int = 512):
        """Initializes the collection with the correct vector size."""
        self._vector_size = vector_size
        if not self._available:
            logger.warning("Qdrant unavailable, skipping collection creation")
            return
        try:
            self._client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
        except Exception as e:
            logger.error(f"Failed to create collection {self.collection_name}: {e}")
            self._available = False

    def upsert(self, ids: List[int], vectors: List[List[float]], payloads: List[Dict]):
        """Upserts vectors and payloads into the collection."""
        if not self._available:
            logger.debug(
                f"Qdrant unavailable, ignoring upsert for {len(payloads)} items"
            )
            return
        try:
            self._client.upsert(
                collection_name=self.collection_name,
                points=models.Batch(ids=ids, vectors=vectors, payloads=payloads),
            )
        except Exception as e:
            logger.error(f"Failed to upsert to {self.collection_name}: {e}")
            self._available = False

    def search(self, vector: List[float], limit: int = 5) -> List[Dict]:
        """Searches for similar vectors and returns payloads."""
        if not self._available:
            logger.debug("Qdrant unavailable, returning empty search results")
            return []
        try:
            hits = self._client.search(
                collection_name=self.collection_name, query_vector=vector, limit=limit
            )
            return [hit.payload for hit in hits]
        except Exception as e:
            logger.error(f"Search failed for {self.collection_name}: {e}")
            self._available = False
            return []

    def delete_by_field(self, field: str, value: str):
        """Deletes points whose payload field matches the provided value."""
        if not self._available:
            return
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key=field,
                                match=models.MatchValue(value=value),
                            )
                        ]
                    )
                ),
            )
        except Exception as e:
            logger.error(f"Delete failed for {self.collection_name}: {e}")


def init_collections():
    """Script to initialize the 3 required collections."""
    client = QdrantClient(host="localhost", port=6333)
    collections = ["docs_index", "behavior_index", "execution_index"]

    for coll in collections:
        print(f"Initializing collection: {coll}...")
        client.recreate_collection(
            collection_name=coll,
            vectors_config=models.VectorParams(
                size=768, distance=models.Distance.COSINE
            ),
        )
    print("All collections initialized.")


if __name__ == "__main__":
    init_collections()
