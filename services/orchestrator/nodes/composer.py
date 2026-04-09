from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_openai import ChatOpenAI
from agents.config import settings
from services.orchestrator.state import AgentState


def composer(state: AgentState) -> AgentState:
    """Generate final answer from verified evidence only."""

    # Build context from evidence
    context_parts = []

    for i, ev in enumerate(state.get("evidence", []), 1):
        context_parts.append(
            f"[Source {i}] {ev['claim']} (confidence: {ev['confidence']:.2f})"
        )

    context = "\n".join(context_parts) if context_parts else "No evidence available."

    # Build system prompt
    system_parts = [
        settings.agentic_system_prompt,
        "\nYou must answer ONLY using the provided evidence.",
        "If evidence is insufficient, state that clearly.",
    ]

    if state.get("behavioral_rules"):
        system_parts.append("\nBehavioral Preferences:")
        for rule in state["behavioral_rules"]:
            system_parts.append(f"- {rule}")

    system_prompt = "\n".join(system_parts)

    # Compose answer
    user_prompt = f"""
Query: {state["user_query"]}

Evidence:
{context}

Generate a complete answer using only the evidence above.
"""

    llm = ChatOpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        model=state.get("model_name", settings.litellm_model),
        temperature=0.3,
        timeout=15,
        max_retries=0,
    )

    try:
        response = llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

        state["final_answer"] = response.content.strip()

    except Exception as e:
        state["final_answer"] = f"Error generating answer: {str(e)}"
        state["error"] = str(e)

    return state
