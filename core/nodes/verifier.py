from core.state import AgentState
from core.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
import json

# Initialize fast LLM via factory
llm = LLMFactory.get_model("fast", temperature=0.0)

def verifier(state: AgentState) -> dict:
    """
    Validates collected evidence against the user's original request.
    If coverage is thin, the graph returns to the planner.
    """
    user_input = state["messages"][-1].content
    evidence = state.get("evidence", [])
    intent = state.get("intent", "chat")
    
    if intent not in ["research", "coding", "artifact"]:
        return {
            "verification_status": "PASSED",
            "errors": [],
            "current_task": "Verification: PASSED"
        }

    # Perform fast verification
    evidence_str = "\n".join([f"- {e['claim']}" for e in evidence]) if evidence else "None"
    system_prompt = f"""
    You are the Verifier.
    User Request: {user_input}
    Collected Evidence: {evidence_str}
    
    Is the collected evidence sufficient to answer the user's request?
    Respond with exactly 'PASSED' or 'FAILED'.
    """
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Evaluate now.")
        ])
        status = "PASSED" if "PASSED" in response.content.upper() else "FAILED"
    except Exception as e:
        status = "FAILED" if not evidence else "PASSED"
        print(f"[Verifier] LLM check failed: {e}")

    errors = ["Missing evidence for task. Retrying..."] if status == "FAILED" else []
        
    return {
        "verification_status": status,
        "errors": errors,
        "current_task": f"Verification: {status}"
    }
