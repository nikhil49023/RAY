from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.orchestrator.graph import build_graph
from services.orchestrator.state import AgentState
from agents.config import settings


class LangGraphOrchestrator:
    """LangGraph-based orchestrator for RAY."""

    def __init__(self):
        self.graph = build_graph()

    def run(
        self,
        query: str,
        session_id: str = "default",
        model_name: str = None,
        stream_callback=None,
    ) -> dict:
        """Execute graph and return result."""

        # Initialize state
        initial_state: AgentState = {
            "user_query": query,
            "session_id": session_id,
            "intent": "chat",
            "behavioral_rules": [],
            "applied_rules": [],
            "plan": {},
            "subtasks": [],
            "doc_rag_results": [],
            "web_rag_results": [],
            "code_results": [],
            "evidence": [],
            "verification_status": "PENDING",
            "verification_reason": "",
            "final_answer": "",
            "artifact_path": "",
            "model_name": model_name or settings.litellm_model,
            "checkpoint_mode": "async",
            "retrieval_attempts": 0,
            "error": "",
        }

        # Execute graph
        try:
            config = {"configurable": {"thread_id": session_id}}

            # Stream execution if callback provided
            if stream_callback:
                for event in self.graph.stream(initial_state, config):
                    stream_callback(event)
                    final_state = event
            else:
                final_state = self.graph.invoke(initial_state, config)

            # Extract result
            return {
                "status": "success",
                "mode": "langgraph",
                "answer": final_state.get("final_answer", ""),
                "artifact_path": final_state.get("artifact_path", ""),
                "evidence": final_state.get("evidence", []),
                "applied_rules": final_state.get("applied_rules", []),
                "verification_status": final_state.get("verification_status", ""),
                "error": final_state.get("error", ""),
            }

        except Exception as e:
            return {
                "status": "error",
                "mode": "langgraph",
                "answer": f"Graph execution failed: {str(e)}",
                "artifact_path": "",
                "evidence": [],
                "applied_rules": [],
                "verification_status": "FAILED",
                "error": str(e),
            }
