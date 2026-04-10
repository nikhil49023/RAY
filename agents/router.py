from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List

from agents.config import settings


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    complexity: int
    primary_provider: str
    primary_model: str
    use_ensemble: bool
    ensemble_models: List[str]
    reason: str


class SemanticRouter:
    def _complexity_score(self, prompt: str) -> int:
        score = 0
        words = len(prompt.split())
        if words > 1000:
            score += 10

        code_signals = [
            "def ",
            "class ",
            "function",
            "debug",
            "compile",
            "traceback",
            "algorithm",
            "sql",
            "docker",
            "json",
            "```",
        ]
        if any(signal in prompt.lower() for signal in code_signals):
            score += 10

        # Non-ASCII text is a lightweight proxy for multilingual/regional prompts.
        if any(ord(ch) > 127 for ch in prompt):
            score += 10

        # Long-context oriented prompts.
        if any(
            k in prompt.lower()
            for k in ["summarize this document", "analyze this report", "full context"]
        ):
            score += 5

        return score

    def _intent(self, prompt: str) -> str:
        lower = prompt.lower()
        if re.search(r"[\u0900-\u097f]", prompt) or any(
            k in lower for k in ["hinglish", "hindi", "indian law", "ipc"]
        ):
            return "regional"
        if any(
            k in lower
            for k in [
                "code",
                "debug",
                "python",
                "javascript",
                "bug",
                "refactor",
                "compile",
            ]
        ):
            return "coding"
        if any(
            k in lower for k in ["image", "video", "diagram", "vision", "multimodal"]
        ):
            return "multimodal"
        if any(k in lower for k in ["creative", "poem", "story", "rewrite"]):
            return "creative"
        return "general"

    def decide(self, prompt: str, prefer_ensemble: bool = False) -> RouteDecision:
        intent = self._intent(prompt)
        complexity = self._complexity_score(prompt)

        # Rule A: regional/cultural prompts.
        if intent == "regional":
            return RouteDecision(
                intent=intent,
                complexity=complexity,
                primary_provider="groq",
                primary_model=settings.groq_model_quality,
                use_ensemble=False,
                ensemble_models=[],
                reason="Regional intent detected; prefer Groq high-quality model and Sarvam for translation/localization.",
            )

        # Rule B: coding + high complexity.
        if intent == "coding" or complexity > 15:
            use_ensemble = (
                prefer_ensemble or settings.enable_ensemble
            ) and complexity >= settings.ensemble_threshold
            ensemble_models = [
                f"groq:{settings.groq_model_strong}",
                f"groq:{settings.groq_model_quality}",
            ]
            return RouteDecision(
                intent=intent,
                complexity=complexity,
                primary_provider="groq",
                primary_model=settings.groq_model_strong,
                use_ensemble=use_ensemble,
                ensemble_models=ensemble_models if use_ensemble else [],
                reason="High complexity or coding prompt; prefer Groq strong model first.",
            )

        # Multimodal prompts.
        if intent == "multimodal":
            return RouteDecision(
                intent=intent,
                complexity=complexity,
                primary_provider="groq",
                primary_model=settings.groq_model_strong,
                use_ensemble=False,
                ensemble_models=[],
                reason="Multimodal intent detected; route to Groq.",
            )

        # Rule C: general low complexity.
        return RouteDecision(
            intent=intent,
            complexity=complexity,
            primary_provider="groq",
            primary_model=settings.groq_model_fast,
            use_ensemble=False,
            ensemble_models=[],
            reason="Low complexity general prompt; route to fast Groq workhorse.",
        )
