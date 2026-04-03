import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_openai import ChatOpenAI
from agents.config import settings
from services.orchestrator.state import AgentState


def planner(state: AgentState) -> AgentState:
    """Generate structured plan with subtasks."""
    
    # Build system prompt with behavioral rules
    system_parts = [settings.agentic_system_prompt]
    if state.get("behavioral_rules"):
        system_parts.append("\nBehavioral Preferences:")
        for rule in state["behavioral_rules"]:
            system_parts.append(f"- {rule}")
    
    system_prompt = "\n".join(system_parts)
    
    # Planning prompt
    user_prompt = f"""
Query: {state['user_query']}
Intent: {state['intent']}

Generate a structured plan with:
1. Subtasks needed
2. Tools required (doc_rag, web_rag, code_runner, artifact_writer)
3. Verification criteria
4. Output schema

Return JSON only.
"""
    
    # Use LiteLLM via langchain
    llm = ChatOpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        model=state.get("model_name", settings.litellm_model),
        temperature=0.1,
    )
    
    try:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        # Parse plan
        plan_text = response.content.strip()
        if plan_text.startswith("```json"):
            plan_text = plan_text[7:]
        if plan_text.endswith("```"):
            plan_text = plan_text[:-3]
        
        plan = json.loads(plan_text)
        state["plan"] = plan
        state["subtasks"] = plan.get("subtasks", [])
        
    except Exception as e:
        # Fallback plan
        state["plan"] = {
            "subtasks": [{"task": "retrieve_context", "tool": "doc_rag"}],
            "verification": "basic",
            "error": str(e)
        }
        state["subtasks"] = state["plan"]["subtasks"]
    
    return state
