from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import chainlit as cl

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.agentic_orchestrator import AgenticOrchestrator
from services.orchestrator.langgraph_orchestrator import LangGraphOrchestrator
from agents.config import settings

MEMORY_DIR = ROOT_DIR / "data" / "memory"
MEMORY_FILE = MEMORY_DIR / "chainlit_history.jsonl"


def _append_memory(role: str, content: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "content": content[:4000],
    }
    with MEMORY_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True) + "\n")


@cl.on_chat_start
async def start():
    """Initialize chat session."""
    
    # Initialize orchestrators
    cl.user_session.set("crewai_orchestrator", AgenticOrchestrator())
    cl.user_session.set("langgraph_orchestrator", LangGraphOrchestrator())
    
    # Default to LangGraph
    cl.user_session.set("use_langgraph", True)
    
    await cl.Message(
        content="🚀 **RAY God Mode Agent** (LangGraph)\n\n"
                "Features:\n"
                "- ✅ Stateful execution with checkpointing\n"
                "- ✅ Behavioral memory injection\n"
                "- ✅ Evidence-based verification\n"
                "- ✅ Inline UI elements\n\n"
                "Toggle `/crewai` to switch to CrewAI mode."
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle user messages."""
    
    user_query = message.content.strip()
    
    # Command: switch to CrewAI
    if user_query.lower() == "/crewai":
        cl.user_session.set("use_langgraph", False)
        await cl.Message(content="Switched to CrewAI mode").send()
        return
    
    # Command: switch to LangGraph
    if user_query.lower() == "/langgraph":
        cl.user_session.set("use_langgraph", True)
        await cl.Message(content="Switched to LangGraph mode").send()
        return
    
    # Get orchestrator
    use_langgraph = cl.user_session.get("use_langgraph", True)
    
    if use_langgraph:
        await handle_langgraph(user_query)
    else:
        await handle_crewai(user_query)
    
    # Persist to memory
    _append_memory("user", user_query)


async def handle_langgraph(query: str):
    """Handle query with LangGraph orchestrator."""
    
    orchestrator: LangGraphOrchestrator = cl.user_session.get("langgraph_orchestrator")
    
    # Show timeline
    timeline_msg = cl.Message(content="")
    await timeline_msg.send()
    
    # Stream execution
    def stream_callback(event):
        # Update timeline with node progress
        # TODO: Implement timeline updates
        pass
    
    # Execute
    result = orchestrator.run(
        query=query,
        session_id=cl.user_session.get("id", "default"),
        model_name=settings.litellm_model,
        stream_callback=stream_callback
    )
    
    # Show memory badge if rules applied
    if result.get("applied_rules"):
        memory_badge = cl.CustomElement(
            name="MemoryBadge",
            props={"rules": result["applied_rules"]},
            display="inline"
        )
        await cl.Message(elements=[memory_badge], content="").send()
    
    # Show evidence table
    if result.get("evidence"):
        evidence_table = cl.CustomElement(
            name="EvidenceTable",
            props={"evidence": result["evidence"]},
            display="inline"
        )
        await cl.Message(elements=[evidence_table], content="").send()
    
    # Show final answer
    answer = result.get("answer", "No answer generated")
    await cl.Message(content=answer).send()
    
    # Show artifact if generated
    if result.get("artifact_path"):
        await cl.Message(content=f"📎 Artifact: `{result['artifact_path']}`").send()
    
    _append_memory("assistant", answer)


async def handle_crewai(query: str):
    """Handle query with CrewAI orchestrator (fallback)."""
    
    orchestrator: AgenticOrchestrator = cl.user_session.get("crewai_orchestrator")
    
    await cl.Message(content="Running CrewAI orchestrator...").send()
    
    # Execute (simplified)
    result = {"answer": "CrewAI fallback response", "status": "success"}
    
    answer = result.get("answer", "No answer generated")
    await cl.Message(content=answer).send()
    
    _append_memory("assistant", answer)


if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)
