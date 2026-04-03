from services.orchestrator.state import AgentState
from services.memory.ollama_embedder import embedder
from services.memory.stores.qdrant_index import QdrantIndex
from services.orchestrator.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
import time

# Initialize the behavior index store
behavior_index = QdrantIndex(collection_name="behavior_index")

# Initialize LLM via factory (fast Llama-3 model for background extraction)
llm = LLMFactory.get_model("fast", temperature=0.1)

def memory_writeback(state: AgentState) -> dict:
    """
    Final extraction node for Mem0-style layered memory updates.
    Converts session preferences into long-term Qdrant vectors.
    """
    user_input = state["messages"][-2].content  # User query
    assistant_output = state["messages"][-1].content  # AI response
    
    system_prompt = """
    You are a Memory Extractor.
    Extract stable preferences, constraints, or corrections from the interaction.
    - Preferences: "Prefer concise answers."
    - Constraints: "Budget is $500."
    - Corrections: "Don't use Python for charts."
    
    Respond in a comma-separated list of extracted rules. 
    If none, respond with "NONE".
    """
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User: {user_input}\nAssistant: {assistant_output}")
    ]
    
    try:
        # Step 1: Extract memory via LLM
        response = llm.invoke(messages)
        extracted_text = response.content.strip()
        
        if extracted_text == "NONE" or not extracted_text:
            return {"current_task": "Memory Writeback: No new rules."}
            
        new_rules = [r.strip() for r in extracted_text.split(",") if r.strip()]
        
        # Step 2: Embed and Upsert into Qdrant
        for rule in new_rules:
            vector = embedder.embed_query(rule)
            behavior_index.upsert(
                ids=[int(time.time() * 1000)],
                vectors=[vector],
                payloads=[{"rule": rule, "type": "behavioral"}]
            )
            
    except Exception as e:
        print(f"Memory writeback error: {e}")
        return {"errors": [f"Memory writeback failed: {e}"]}
    
    return {
        "behavioral_memories": new_rules,
        "current_task": f"Memory Writeback Complete: {len(new_rules)} rules added."
    }
