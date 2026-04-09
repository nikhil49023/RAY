import time
from typing import List
from core.llm_factory import LLMFactory
from core.state import AgentState
from langchain_core.messages import HumanMessage, SystemMessage

def ollama_specialist(state: AgentState) -> dict:
    """
    Optional specialist node that uses local Ollama to compress or analyze 
    large volumes of research results before final composition.
    Triggers if evidence count > 8 or total chars > 5000.
    """
    evidence = state.get("evidence", [])
    total_chars = sum(len(e.get("claim", "")) for e in evidence)
    
    # Trigger condition: Volume-based offloading to local Llama-3
    if len(evidence) <= 8 and total_chars < 5000:
        return {"current_task": "Ollama Specialist Bypass (Low Volume)"}
        
    t0 = time.perf_counter()
    
    # Initialize Ollama model
    llm = LLMFactory.get_model(role="primary", model_id="ollama/llama3")
    
    evidence_text = "\n".join([f"[{i}] {e.get('source')}: {e.get('claim')}" for i, e in enumerate(evidence)])
    
    system_prompt = """
    You are the Ollama Specialist. Your task is to analyze and compress a large volume of research evidence 
    into a structured, high-density summary for the primary reasoning engine.
    
    Focus on:
    1. Identifying cross-source correlations.
    2. Filtering out redundant noise.
    3. High-density factual extraction.
    4. Maintaining academic rigor.
    """
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this research corpus:\n\n{evidence_text}")
        ])
        
        # We add the specialist analysis as a new piece of high-confidence evidence
        specialist_brief = {
            "source": "Local Ollama Analysis",
            "claim": response.content,
            "type": "analysis",
            "confidence": 0.98
        }
        
        elapsed = time.perf_counter() - t0
        return {
            "evidence": evidence + [specialist_brief],
            "current_task": f"Ollama Analysis Complete ({len(evidence)} items compressed)",
            "node_timings": {**state.get("node_timings", {}), "ollama_specialist": round(elapsed, 3)}
        }
    except Exception as e:
        print(f"[ollama_specialist] Error: {e}")
        return {"current_task": "Ollama Analysis Failed"}
