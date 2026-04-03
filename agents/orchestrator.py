from __future__ import annotations

import json
import importlib.util
from typing import Dict

import fire

from agents.api_handlers import ChatMessage, MultiProviderClients
from agents.config import settings
from agents.router import SemanticRouter
from agents.skills import SkillToolkit


class PersonalAgent:
    def __init__(self) -> None:
        self.clients = MultiProviderClients()
        self.router = SemanticRouter()
        self.skills = SkillToolkit()

    def research(self, url: str, crawl: bool = False, limit: int = 200) -> str:
        """Scrape or crawl a URL with Firecrawl and return compact JSON."""
        if crawl:
            data = self.clients.crawl_url(url, limit=limit)
        else:
            data = self.clients.scrape_url(url)
        return json.dumps(data, indent=2, ensure_ascii=True)

    def analyze(self, prompt: str) -> str:
        """Analyze content with Groq first, then fallback chain as needed."""
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a strict analyst. Use explicit reasoning, state assumptions, and avoid hallucinations. "
                    "If uncertain, say unknown."
                ),
            ),
            ChatMessage(role="user", content=prompt),
        ]
        return self.clients.groq_chat(messages, model=settings.groq_model_quality, temperature=0.0)

    def explain(self, content: str) -> str:
        """Explain raw findings in concise bullet points."""
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a teacher. Explain the provided content in clear bullet points, "
                    "call out key metrics, and avoid unsupported claims."
                ),
            ),
            ChatMessage(role="user", content=content),
        ]
        return self.clients.groq_chat(messages, model=settings.research_model_groq, temperature=0.0)

    def visualize(self, data: str, chart: str = "bar") -> str:
        """Generate runnable HTML for an interactive chart artifact."""
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a UI developer. Generate a single HTML file with embedded JavaScript that renders "
                    f"an interactive {chart} chart from the given data. Return only HTML."
                ),
            ),
            ChatMessage(role="user", content=data),
        ]
        return self.clients.groq_chat(messages, model=settings.groq_model_quality, temperature=0.0)

    def translate(self, text: str, target_language_code: str = "gu-IN", source_language_code: str = "auto") -> str:
        """Translate text using Sarvam."""
        response = self.clients.translate(text, target_language_code, source_language_code)
        return json.dumps(response, indent=2, ensure_ascii=True)

    def run_pipeline(self, url: str, chart: str = "bar", target_language_code: str = "gu-IN") -> Dict[str, str]:
        """Research -> analyze -> explain -> visualize -> translate summary."""
        research_json = self.research(url, crawl=False)
        analysis = self.analyze(f"Analyze this research data and list trends as JSON:\n{research_json}")
        explanation = self.explain(analysis)
        html = self.visualize(analysis, chart=chart)
        translation = self.translate(explanation, target_language_code=target_language_code)
        return {
            "research": research_json,
            "analysis": analysis,
            "explanation": explanation,
            "visualization_html": html,
            "translation": translation,
        }

    def ask(self, prompt: str, prefer_ensemble: bool = False, system_prompt: str | None = None) -> Dict[str, str]:
        """Dynamic semantic routing across Groq/OpenRouter/Sarvam strategy."""
        decision = self.router.decide(prompt, prefer_ensemble=prefer_ensemble)

        resolved_system_prompt = (system_prompt or settings.agentic_system_prompt).strip()
        system_msg = ChatMessage(
            role="system",
            content=resolved_system_prompt
            or "You are a factual assistant. Be concise, avoid hallucinations, and clearly mark uncertainty.",
        )
        user_msg = ChatMessage(role="user", content=prompt)
        messages = [system_msg, user_msg]

        if decision.use_ensemble and decision.ensemble_models:
            drafts = []
            for tagged_model in decision.ensemble_models:
                provider, model = tagged_model.split(":", 1)
                if provider == "openrouter":
                    drafts.append(self.clients.openrouter_chat(messages, model=model, temperature=0.0))
                else:
                    drafts.append(self.clients.groq_chat(messages, model=model, temperature=0.0))

            synthesis_prompt = (
                "Original prompt:\n"
                + prompt
                + "\n\nDraft 1:\n"
                + drafts[0]
                + "\n\nDraft 2:\n"
                + drafts[1]
                + "\n\nDraft 3:\n"
                + drafts[2]
                + "\n\nCombine the best parts into one coherent final answer and resolve contradictions."
            )
            final_answer = self.clients.groq_chat(
                [
                    ChatMessage(role="system", content="You are a synthesis judge. Return one best final answer."),
                    ChatMessage(role="user", content=synthesis_prompt),
                ],
                model=settings.groq_model_fast,
                temperature=0.0,
            )
        else:
            if decision.primary_provider == "openrouter":
                final_answer = self.clients.openrouter_chat(messages, model=decision.primary_model, temperature=0.0)
            else:
                final_answer = self.clients.groq_chat(messages, model=decision.primary_model, temperature=0.0)

        return {
            "route_intent": decision.intent,
            "route_complexity": str(decision.complexity),
            "route_provider": decision.primary_provider,
            "route_model": decision.primary_model,
            "route_reason": decision.reason,
            "answer": final_answer,
        }

    def crew_assist(self, objective: str) -> Dict[str, str]:
        """Optional CrewAI workflow for complex tasks. Install crewai to enable."""
        if importlib.util.find_spec("crewai") is None:
            return {
                "status": "disabled",
                "note": "CrewAI is not installed. Install with: pip install crewai",
                "objective": objective,
            }

        # Lightweight decomposition pipeline while keeping the current provider router.
        planner = self.ask(f"Break this objective into 3 clear execution steps: {objective}")
        executor = self.ask(f"Execute this objective using the plan below and return concise output. Plan: {planner['answer']}")
        reviewer = self.ask(
            "Review this output for correctness and missing assumptions. "
            f"Objective: {objective}\nOutput: {executor['answer']}"
        )

        return {
            "status": "ok",
            "plan": planner["answer"],
            "result": executor["answer"],
            "review": reviewer["answer"],
        }

    def draft_document(self, title: str, markdown: str, output_format: str = "docx") -> Dict[str, str]:
        """Draft a document artifact as PDF or DOCX from markdown."""
        return self.skills.generate_document(title=title, markdown=markdown, output_format=output_format)

    def illustrate(self, prompt: str, provider: str = "huggingface") -> Dict[str, str]:
        """Generate an image artifact through a free hosted image API."""
        return self.skills.illustrate(prompt=prompt, provider=provider)


if __name__ == "__main__":
    fire.Fire(PersonalAgent)
