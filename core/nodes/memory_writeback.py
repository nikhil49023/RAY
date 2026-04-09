from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from services.memory.ollama_embedder import embedder
from services.memory.semantic_memory import write_semantic_memory
from services.memory.stores.qdrant_index import QdrantIndex
from core.llm_factory import LLMFactory
from core.state import AgentState

behavior_index = QdrantIndex(collection_name="behavior_index")
llm: Any = None


def _resolve_llm() -> Any:
    global llm
    if llm is None:
        llm = LLMFactory.get_model("fast", temperature=0.1)
    return llm


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _latest_user_and_assistant(state: AgentState) -> tuple[str, str]:
    user_input = ""
    assistant_output = state.get("answer", "") or ""
    for message in reversed(state.get("messages", [])):
        if not assistant_output and isinstance(message, AIMessage):
            assistant_output = _message_text(message.content)
        if not user_input and isinstance(message, HumanMessage):
            user_input = _message_text(message.content)
        if user_input and assistant_output:
            break
    return user_input.strip(), assistant_output.strip()


def memory_writeback(state: AgentState) -> dict:
    """
    Persist the latest turn into semantic memory and extract durable preferences.
    """
    user_input, assistant_output = _latest_user_and_assistant(state)
    session_id = str(state.get("session_id", "") or "").strip()
    scraped_data = state.get("scraped_data", []) or []
    deep_research_summary = str(state.get("deep_research_summary", "") or "").strip()
    supplemental_entries: list[dict[str, str]] = []
    for item in scraped_data:
        url = str(item.get("url", "")).strip()
        content = str(item.get("content", "")).strip()
        if url and content:
            supplemental_entries.append({
                "type": "document",
                "source": "web_search",
                "content": f"Scraped from {url}\n\n{content}",
            })
    if deep_research_summary:
        supplemental_entries.append({
            "type": "fact",
            "source": "web_search",
            "content": deep_research_summary,
        })

    memory_writes = write_semantic_memory(
        user_input=user_input,
        assistant_output=assistant_output,
        session_id=session_id,
        source="conversation",
        supplemental_entries=supplemental_entries,
    )

    if not user_input and not assistant_output:
        return {"current_task": "Memory writeback skipped"}

    system_prompt = """
    You are a Memory Extractor.
    Extract stable preferences, constraints, or corrections from the interaction.
    - Preferences: "Prefer concise answers."
    - Constraints: "Budget is $500."
    - Corrections: "Don't use Python for charts."
    
    Respond in a comma-separated list of extracted rules. 
    If none, respond with "NONE".
    """
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User: {user_input}\nAssistant: {assistant_output}")
    ]

    try:
        response = _resolve_llm().invoke(messages)
        extracted_text = _message_text(response.content).strip()

        if extracted_text == "NONE" or not extracted_text:
            return {
                "memory_writes": memory_writes,
                "current_task": "Memory writeback complete",
            }

        new_rules = [r.strip() for r in extracted_text.split(",") if r.strip()]

        for rule in new_rules:
            vector = embedder.embed_query(rule)
            point_id = int(time.time_ns() % 9_223_372_036_854_775_000)
            behavior_index.upsert(
                ids=[point_id],
                vectors=[vector],
                payloads=[{"rule": rule, "type": "behavioral", "timestamp": time.time()}],
            )

    except Exception as e:
        return {
            "errors": [f"Memory writeback failed: {e}"],
            "memory_writes": memory_writes,
        }

    return {
        "behavioral_memories": new_rules,
        "memory_writes": memory_writes,
        "current_task": f"Memory writeback complete: {len(new_rules)} rules added."
    }
