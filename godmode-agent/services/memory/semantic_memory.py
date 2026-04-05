from __future__ import annotations

from datetime import datetime, timezone
import re
import time
from typing import Any, Dict

from services.memory.ollama_embedder import embedder
from services.memory.stores.qdrant_index import QdrantIndex


DEFAULT_BEHAVIORAL_RULES = [
    "Prefer concise, high-confidence explanations.",
    "Cite sources for external or web-derived claims when URLs are available.",
]

MAX_CHUNK_CHARS = 1800

behavior_index = QdrantIndex(collection_name="behavior_index")
execution_index = QdrantIndex(collection_name="execution_index")


def _extract_entities(text: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][A-Za-z0-9&.+-]*(?:\s+[A-Z][A-Za-z0-9&.+-]*){0,2}\b", text or "")
    unique: list[str] = []
    for value in matches:
        cleaned = value.strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique[:12]


def _topic_tags(text: str) -> list[str]:
    tags = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower()):
        if token not in tags:
            tags.append(token)
    return tags[:8]


def _chunk_text(text: str, *, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    content = (text or "").strip()
    if not content:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        paragraphs = [content]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        for start in range(0, len(paragraph), max_chars):
            chunks.append(paragraph[start:start + max_chars].strip())
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def retrieve_semantic_memory(query: str, *, top_k: int = 5) -> Dict[str, Any]:
    clean_query = (query or "").strip()
    if not clean_query:
        return {
            "behavioral_memories": list(DEFAULT_BEHAVIORAL_RULES),
            "memory_hits": [],
            "memory_context": "",
        }

    try:
        query_vector = embedder.embed_query(clean_query)
        execution_hits = execution_index.search(vector=query_vector, limit=max(1, top_k))
        behavior_hits = behavior_index.search(vector=query_vector, limit=min(max(1, top_k), 5))
    except Exception:
        return {
            "behavioral_memories": list(DEFAULT_BEHAVIORAL_RULES),
            "memory_hits": [],
            "memory_context": "",
        }

    behavioral_memories = [
        str(hit.get("rule", "")).strip()
        for hit in behavior_hits
        if str(hit.get("rule", "")).strip()
    ] or list(DEFAULT_BEHAVIORAL_RULES)

    memory_hits: list[dict] = []
    for hit in execution_hits:
        content = str(hit.get("content") or hit.get("summary") or hit.get("text") or "").strip()
        if not content:
            continue
        memory_hits.append({
            "type": str(hit.get("type") or "conversation"),
            "timestamp": str(hit.get("timestamp") or ""),
            "source": str(hit.get("source") or ""),
            "content": content[:MAX_CHUNK_CHARS],
            "entities": hit.get("entities") or [],
        })

    memory_context = "\n\n".join(
        f"[{item['type']} | {item['timestamp'] or 'unknown'}]\n{item['content']}"
        for item in memory_hits
    )[:6000]

    return {
        "behavioral_memories": behavioral_memories,
        "memory_hits": memory_hits,
        "memory_context": memory_context,
    }


def write_semantic_memory(
    *,
    user_input: str,
    assistant_output: str,
    session_id: str = "",
    source: str = "conversation",
    supplemental_entries: list[dict[str, str]] | None = None,
) -> list[dict]:
    timestamp = datetime.now(timezone.utc).isoformat()
    records: list[dict] = []

    for memory_type, raw_content, memory_source in (
        ("conversation", user_input, "user_input"),
        ("conversation", assistant_output, "assistant_output"),
    ):
        text = (raw_content or "").strip()
        if not text:
            continue
        for chunk in _chunk_text(text):
            records.append({
                "type": memory_type,
                "content": chunk,
                "timestamp": timestamp,
                "source": memory_source if source == "conversation" else source,
                "topic_tags": _topic_tags(chunk),
                "session_id": session_id,
                "entities": _extract_entities(chunk),
            })

    for entry in supplemental_entries or []:
        raw_content = str(entry.get("content") or "").strip()
        if not raw_content:
            continue
        memory_type = str(entry.get("type") or "fact")
        memory_source = str(entry.get("source") or source)
        for chunk in _chunk_text(raw_content):
            records.append({
                "type": memory_type,
                "content": chunk,
                "timestamp": timestamp,
                "source": memory_source,
                "topic_tags": _topic_tags(chunk),
                "session_id": session_id,
                "entities": _extract_entities(chunk),
            })

    if not records:
        return []

    try:
        vectors = embedder.embed_documents([item["content"] for item in records])
        ids = [int((time.time_ns() + index) % 9_223_372_036_854_775_000) for index in range(len(records))]
        execution_index.upsert(ids=ids, vectors=vectors, payloads=records)
    except Exception:
        return []

    return records
