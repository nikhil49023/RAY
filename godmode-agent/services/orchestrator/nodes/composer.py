"""
composer.py — Final Answer Generator
--------------------------------------
Synthesizes evidence into a polished response.
Sets state["answer"] directly (not just messages).
Uses the user-selected brain.
"""

import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from services.orchestrator.assistant_contract import build_assistant_contract
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.runtime import load_user_settings
from services.orchestrator.visual_output import build_visual_output_guidance

# Configure logging
logger = logging.getLogger("ray.composer")


def composer(state: AgentState) -> dict:
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")
    settings = load_user_settings()
    ui_settings = settings.get("ui", {})
    temperature = float(state.get("temperature", settings.get("temperature", 0.1)))

    logger.info(f"Composing response with model: {model_id}")

    try:
        llm = LLMFactory.get_model(model_id=model_id, temperature=temperature)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return {
            "answer": f"⚠️ Failed to initialize model '{model_id}': {e}\n\nPlease check your API key in Settings or select a different model.",
            "messages": [AIMessage(content=f"Model initialization failed: {e}")],
            "current_task": "Error",
            "thinking_log": [{
                "node": "composer",
                "title": "Model initialization failed",
                "detail": str(e),
                "provider": model_id.split("/", 1)[0],
                "model": model_id,
            }],
        }

    query = state.get("rewritten_query") or state["messages"][-1].content
    evidence = state.get("evidence", [])
    intent = state.get("intent", "chat")
    plan = state.get("plan", "")
    agent_mode = state.get("agent_mode", "standard")
    visuals_enabled = bool(state.get("visuals_enabled", ui_settings.get("renderVisualsInline", False)))
    memory_context = state.get("memory_context", "")
    behavioral_memories = state.get("behavioral_memories", [])
    firecrawl_summary = state.get("firecrawl_summary", "")
    scraped_data = state.get("scraped_data", [])

    logger.debug(f"Composing for intent={intent}, mode={agent_mode}, evidence_count={len(evidence)}")

    # Build evidence block
    if evidence:
        ev_lines = []
        for i, e in enumerate(evidence, 1):
            src = e.get("source", "unknown")
            title = e.get("title", "") or src
            url = e.get("url", "")
            claim = e.get("claim", "")[:300]
            citation = f"[Source: {title} — {url}]" if url else f"[Source: {src}]"
            ev_lines.append(f"[{i}] {citation} {claim}")
        evidence_block = "\n".join(ev_lines)
    else:
        evidence_block = "No external evidence was retrieved."

    output_rules = build_visual_output_guidance(visuals_enabled=visuals_enabled)

    system_prompt = f"""{build_assistant_contract(
        visuals_enabled=visuals_enabled,
        memory_context=memory_context,
        behavioral_memories=behavioral_memories,
    )}

You are composing the final answer for the user.

RULES:
1. Be precise, rigorous, and information-dense. No filler.
2. Ground claims in the provided evidence and retrieved memory when available.
3. Cite external claims inline as [Source: Title — URL] whenever a URL is available.
4. If evidence was used, end with a `## Sources` section that lists the unique source URLs.
5. If no evidence is provided, rely on your training knowledge and say so.
6. Never reveal hidden chain-of-thought. The UI will show system-generated execution logs separately.
{output_rules}
7. Use markdown formatting: headers, bold, lists, code blocks.
8. Keep visual blocks self-contained and syntactically valid.
9. Always be helpful, thorough, and accurate.

CONTEXT:
Intent: {intent}
Mode: {agent_mode}
Plan: {plan[:500] if plan else 'None'}
Preferred research output: {ui_settings.get("researchOutput", "document")}
Visual mode enabled: {visuals_enabled}
Retrieved memory available: {bool(memory_context)}
Firecrawl scraped pages: {len(scraped_data)}
Firecrawl synthesis available: {bool(firecrawl_summary)}

EVIDENCE:
{evidence_block}

FIRECRAWL SYNTHESIS:
{firecrawl_summary[:4000] if firecrawl_summary else 'No Firecrawl scrape summary available.'}"""

    try:
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
        answer = resp.content
        logger.info(f"Response composed successfully ({len(str(answer))} chars)")
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        answer = f"⚠️ The model encountered an error generating a response: {e}\n\nPlease try again or switch to a different model."

    return {
        "answer": answer,
        "messages": [AIMessage(content=answer)],
        "current_task": "Response ready",
        "thinking_log": [{
            "node": "composer",
            "title": "Final response composed",
            "detail": "Prepared a visual response." if visuals_enabled else "Prepared a plain markdown response.",
            "provider": model_id.split("/", 1)[0],
            "model": model_id,
        }],
    }
