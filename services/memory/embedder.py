from pathlib import Path
import sys
import requests

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings


class OllamaEmbedder:
    """Local embeddings via Ollama."""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url.strip().rstrip("/")
        self.model = settings.rag_embedding_model
    
    def embed(self, text: str) -> list:
        """Generate embedding for text."""
        endpoints = [self.base_url]
        
        # Add localhost fallback if using container name
        if "://ollama" in self.base_url:
            endpoints.append(self.base_url.replace("://ollama", "://localhost"))
        
        for base in endpoints:
            for endpoint, payload in [
                ("/api/embeddings", {"model": self.model, "prompt": text}),
                ("/api/embed", {"model": self.model, "input": text}),
            ]:
                try:
                    response = requests.post(
                        base + endpoint,
                        json=payload,
                        timeout=60
                    )
                    response.raise_for_status()
                    body = response.json()
                    
                    if isinstance(body.get("embedding"), list):
                        return body["embedding"]
                    if isinstance(body.get("embeddings"), list) and body["embeddings"]:
                        first = body["embeddings"][0]
                        if isinstance(first, list):
                            return first
                except Exception:
                    continue
        
        raise RuntimeError(f"Failed to generate embedding from {self.base_url}")
    
    def embed_batch(self, texts: list) -> list:
        """Generate embeddings for multiple texts."""
        return [self.embed(text) for text in texts]
