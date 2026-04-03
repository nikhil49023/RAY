"""
composer.py — Final Answer Generator
--------------------------------------
Synthesizes evidence into a polished response.
Sets state["answer"] directly (not just messages).
Uses the user-selected brain.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from services.orchestrator.state import AgentState
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.runtime import load_user_settings


def composer(state: AgentState) -> dict:
    model_id = state.get("selected_model", "groq/llama-3.3-70b-versatile")
    settings = load_user_settings()
    ui_settings = settings.get("ui", {})
    temperature = float(state.get("temperature", settings.get("temperature", 0.1)))
    llm = LLMFactory.get_model(model_id=model_id, temperature=temperature)

    query = state.get("rewritten_query") or state["messages"][-1].content
    evidence = state.get("evidence", [])
    intent = state.get("intent", "chat")
    plan = state.get("plan", "")
    agent_mode = state.get("agent_mode", "standard")

    # Build evidence block
    if evidence:
        ev_lines = []
        for i, e in enumerate(evidence, 1):
            src = e.get("source", "unknown")
            url = e.get("url", "")
            claim = e.get("claim", "")[:300]
            ev_lines.append(f"[{i}] ({src}) {claim}" + (f"\n    URL: {url}" if url else ""))
        evidence_block = "\n".join(ev_lines)
    else:
        evidence_block = "No external evidence was retrieved."

    system_prompt = f"""\
You are a God-Mode scientific assistant. Synthesize the best possible answer.

RULES:
1. Be precise, rigorous, and information-dense. No filler.
2. Ground claims in the provided evidence. Cite sources as [1], [2], etc.
3. If no evidence is provided, rely on your training knowledge and say so.
4. Never reveal hidden chain-of-thought. The UI will show system-generated execution logs separately.
5. For research mode, put the detailed research brief inside:
   <document: Research Brief>
   content here
   </document>
6. For long-form outputs (reports, essays, code >50 lines), wrap in:
   <canvas: Document Title>
   content here
   </canvas>
7. For charts or comparisons, use a ```chart code block with strict JSON:
   {{
     "type": "bar" or "line",
     "title": "Short chart title",
     "labels": ["label 1", "label 2"],
     "series": [{{"label": "Series 1", "data": [1, 2]}}]
   }}
8. Use ```mermaid code blocks for diagrams when they add clarity.
9. Use markdown formatting: headers, bold, lists, code blocks.
10. Always be helpful, thorough, and accurate.

CONTEXT:
Intent: {intent}
Mode: {agent_mode}
Plan: {plan[:500] if plan else 'None'}
Preferred research output: {ui_settings.get("researchOutput", "document")}

EVIDENCE:
{evidence_block}"""

    try:
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
        answer = resp.content
    except Exception as e:
        answer = f"⚠️ The model encountered an error generating a response: {e}\n\nPlease try again or switch to a different model."

    return {
        "answer": answer,
        "messages": [AIMessage(content=answer)],
        "current_task": "Response ready",
        "thinking_log": [{
            "node": "composer",
            "title": "Final response composed",
            "detail": f"Rendered a {ui_settings.get('researchOutput', 'document')} friendly answer with inline visual-block support.",
            "provider": model_id.split("/", 1)[0],
            "model": model_id,
        }],
    }
