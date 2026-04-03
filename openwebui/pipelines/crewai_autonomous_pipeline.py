from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.agentic_orchestrator import AgenticOrchestrator


class Pipeline:
    def __init__(self) -> None:
        self.name = "RAY CrewAI Autonomous Pipeline"
        self.orchestrator = AgenticOrchestrator()

    async def on_startup(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def on_valves_updated(self) -> None:
        return None

    def _extract_prompt(self, body: dict[str, Any]) -> str:
        messages = body.get("messages") or []
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            text = item.get("text")
                            if text:
                                parts.append(str(text))
                    content = "\n".join(parts)
                return str(content).strip()
        return ""

    def _render_response(self, result: dict[str, Any]) -> str:
        if result.get("status") != "ok":
            return "Autonomous pipeline failed to execute.\n\n" + str(result)

        mode = result.get("mode", "unknown")
        answer = str(result.get("answer", "")).strip()
        artifact = str(result.get("visualization_artifact", "")).strip()
        reason = str(result.get("reason", "")).strip()

        lines = [
            f"Mode: {mode}",
        ]
        if reason:
            lines.append(f"Reason: {reason}")
        if answer:
            lines.extend(["", answer])
        if artifact:
            lines.extend(["", f"Visualization artifact: {artifact}"])
        return "\n".join(lines)

    def _stream_text(self, text: str) -> Iterable[str]:
        for line in text.splitlines(keepends=True):
            yield line

    def pipe(self, body: dict[str, Any]) -> str | Iterable[str]:
        prompt = self._extract_prompt(body)
        if not prompt:
            return "No user prompt found in the request body."

        result = self.orchestrator.run_goal(prompt)
        rendered = self._render_response(result)

        if body.get("stream"):
            return self._stream_text(rendered)
        return rendered
