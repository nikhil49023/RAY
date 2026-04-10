from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_openai import ChatOpenAI
from agents.config import settings


class FallbackPolicy:
    """Provider fallback via LiteLLM routing."""
    
    def __init__(self):
        self.primary_model = settings.litellm_model
        self.fallback_models = [
            settings.groq_model_quality,
            settings.ollama_fallback_model
        ]
    
    def get_llm(self, model_name: str = None):
        """Get LLM with fallback chain."""
        
        model = model_name or self.primary_model
        
        return ChatOpenAI(
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key,
            model=model,
            temperature=0.3,
        )
    
    def invoke_with_fallback(self, messages: list, model_name: str = None):
        """Invoke LLM with automatic fallback on failure."""
        
        models_to_try = [model_name or self.primary_model] + self.fallback_models
        last_error = None
        
        for model in models_to_try:
            try:
                llm = self.get_llm(model)
                response = llm.invoke(messages)
                return response.content
            except Exception as e:
                last_error = e
                continue
        
        raise RuntimeError(f"All models failed. Last error: {last_error}")
