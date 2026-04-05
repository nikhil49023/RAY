import ollama
from typing import List
import logging

logger = logging.getLogger("ray.embedder")


class OllamaEmbedder:
    """
    Direct client for Ollama embeddings.
    Strictly bypasses LiteLLM to optimize for local 4GB VRAM usage.
    Includes fallback for when Ollama is unavailable.
    """

    def __init__(
        self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"
    ):
        self.client = ollama.Client(host=host)
        self.model = model
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is available and has the model."""
        try:
            self.client.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        if not self._available:
            return self._fallback_embedding(text)
        try:
            response = self.client.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            logger.warning(f"Ollama embedding failed, using fallback: {e}")
            self._available = False
            return self._fallback_embedding(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents."""
        if not self._available:
            return [self._fallback_embedding(t) for t in texts]
        embeddings = []
        for text in texts:
            try:
                response = self.client.embeddings(model=self.model, prompt=text)
                embeddings.append(response["embedding"])
            except Exception as e:
                logger.warning(f"Ollama embedding failed for doc, using fallback: {e}")
                embeddings.append(self._fallback_embedding(text))
        return embeddings

    def _fallback_embedding(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-embedding when Ollama unavailable."""
        import hashlib

        hash_input = text.encode() + self.model.encode()
        hash_digest = hashlib.sha256(hash_input).digest()
        return [float(b) / 255.0 * 2.0 - 1.0 for b in hash_digest[:256]] + [0.0] * (
            512 - 256
        )


embedder = OllamaEmbedder()
