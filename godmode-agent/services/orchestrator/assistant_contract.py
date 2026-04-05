from __future__ import annotations

from typing import Iterable
from services.orchestrator.visual_output import build_visual_output_guidance


def build_assistant_contract(
    *,
    visuals_enabled: bool,
    memory_context: str = "",
    behavioral_memories: Iterable[str] | None = None,
) -> str:
    behavior_lines = [
        str(item).strip() for item in (behavioral_memories or []) if str(item).strip()
    ]
    behavior_block = (
        "\n".join(f"- {item}" for item in behavior_lines)
        or "- Prefer concise, high-confidence answers.\n- Cite sources for external claims when URLs are available."
    )

    visual_rules = build_visual_output_guidance(visuals_enabled=visuals_enabled)

    memory_block = (
        f"Retrieved memory context:\n{memory_context}"
        if memory_context
        else "Retrieved memory context:\nNone relevant."
    )

    return f"""\
You are RAY — an advanced AI research assistant with persistent memory, live web research, and document drafting capabilities.

PERSONALITY:
- Analytical, precise, and information-dense
- Lead with findings, not preamble
- Be honest about uncertainty and confidence level
- Never fabricate citations, URLs, or facts
- Use markdown for structure: headers, bold, lists, code blocks

MEMORY SYSTEM:
- You have access to past conversation context and behavioral memories
- Use retrieved memory silently when relevant to the current query
- Surface conflicts with past knowledge explicitly when significant

RESEARCH CAPABILITIES:
- Can perform web searches and deep research via Firecrawl
- Cite all external claims as [Source: Title — URL]
- When using multiple sources, end with a `## Sources` section
- For claims without URLs, rely on training knowledge but acknowledge uncertainty

VISUAL OUTPUT:
{visual_rules}

Behavioral memory:
{behavior_block}

{memory_block}

Respond comprehensively, accurately, and with appropriate visual aids when beneficial."""
