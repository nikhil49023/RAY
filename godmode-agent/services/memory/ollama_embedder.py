import ollama
from typing import List

class OllamaEmbedder:
    """
    Direct client for Ollama embeddings.
    Strictly bypasses LiteLLM to optimize for local 4GB VRAM usage.
    """
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.client = ollama.Client(host=host)
        self.model = model

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        response = self.client.embeddings(model=self.model, prompt=text)
        return response['embedding']

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents."""
        embeddings = []
        for text in texts:
            response = self.client.embeddings(model=self.model, prompt=text)
            embeddings.append(response['embedding'])
        return embeddings

# Global instance for shared use
embedder = OllamaEmbedder()
