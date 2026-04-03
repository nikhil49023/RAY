from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

import requests

from agents.config import settings


@dataclass(frozen=True)
class MemoryStatus:
    ready: bool
    backend: str
    detail: str


class BehavioralMemory:
    """Persistent behavioral memory backed by Chroma with local JSON fallback."""

    def __init__(self) -> None:
        self.root_dir = Path(__file__).resolve().parents[1]
        self.memory_dir = self.root_dir / "data" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.rules_file = self.memory_dir / "behavior_rules.jsonl"
        self.collection_name = settings.behavior_memory_collection
        self.local_chroma_path = (
            Path(settings.rag_chroma_local_path)
            if Path(settings.rag_chroma_local_path).is_absolute()
            else self.root_dir / settings.rag_chroma_local_path
        )

    def _embedding_endpoints(self) -> List[str]:
        configured = settings.ollama_base_url.strip().rstrip("/")
        endpoints = [configured] if configured else []
        if "://ollama" in configured:
            endpoints.append(configured.replace("://ollama", "://localhost"))
        return [item for index, item in enumerate(endpoints) if item and item not in endpoints[:index]]

    def _embed(self, text: str) -> List[float]:
        errors: List[str] = []
        for base in self._embedding_endpoints():
            for endpoint, payload in [
                ("/api/embeddings", {"model": settings.rag_embedding_model, "prompt": text}),
                ("/api/embed", {"model": settings.rag_embedding_model, "input": text}),
            ]:
                try:
                    response = requests.post(base + endpoint, json=payload, timeout=60)
                    response.raise_for_status()
                    body = response.json()
                    if isinstance(body.get("embedding"), list):
                        return body["embedding"]
                    if isinstance(body.get("embeddings"), list) and body["embeddings"]:
                        first = body["embeddings"][0]
                        if isinstance(first, list):
                            return first
                    raise RuntimeError("embedding payload missing")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{base}{endpoint}: {type(exc).__name__}: {exc}")
        raise RuntimeError("Unable to generate embeddings. " + " | ".join(errors))

    def _get_chroma_client(self) -> Tuple[Any, str]:
        if importlib.util.find_spec("chromadb") is None:
            raise RuntimeError("chromadb not installed")

        chromadb = importlib.import_module("chromadb")
        errors: List[str] = []

        try:
            remote = chromadb.HttpClient(host=settings.rag_chroma_host, port=settings.rag_chroma_port)
            remote.heartbeat()
            return remote, "http"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"http://{settings.rag_chroma_host}:{settings.rag_chroma_port}: {type(exc).__name__}: {exc}")

        try:
            local = chromadb.PersistentClient(path=str(self.local_chroma_path))
            local.heartbeat()
            return local, "local"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{self.local_chroma_path}: {type(exc).__name__}: {exc}")

        raise RuntimeError("Chroma unavailable. " + " | ".join(errors))

    def status(self) -> MemoryStatus:
        try:
            _, backend = self._get_chroma_client()
            return MemoryStatus(ready=True, backend=backend, detail="Chroma behavioral memory is reachable.")
        except Exception as exc:  # noqa: BLE001
            return MemoryStatus(ready=False, backend="json_fallback", detail=f"Using JSON fallback: {exc}")

    def _append_rule_file(self, rule: str, source: str) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rule": rule,
            "source": source,
        }
        with self.rules_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _read_rule_file(self) -> List[str]:
        if not self.rules_file.exists():
            return []
        values: List[str] = []
        for line in self.rules_file.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            rule = str(record.get("rule", "")).strip()
            if rule:
                values.append(rule)
        return values

    def _normalize_rule(self, text: str) -> str:
        value = re.sub(r"\s+", " ", text).strip()
        value = re.sub(r"^(please|no|note|remember)\s*[:,\-]?\s*", "", value, flags=re.IGNORECASE)
        return value[:400]

    def _extract_rules(self, text: str) -> List[str]:
        if not text.strip():
            return []

        phrases = re.split(r"[.\n!?]+", text)
        signals = [
            "always",
            "never",
            "prefer",
            "avoid",
            "minimalist",
            "use ",
            "do not",
            "don't",
            "assume",
            "my style",
            "for me",
            "when you",
            "remember",
            "from now on",
            "explain to me",
        ]
        collected: List[str] = []
        for phrase in phrases:
            item = self._normalize_rule(phrase)
            lowered = item.lower()
            if len(item) < 14:
                continue
            if any(signal in lowered for signal in signals):
                collected.append(item)

        unique: List[str] = []
        seen = set()
        for row in collected:
            key = row.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

    def capture_feedback(self, user_text: str, source: str = "chat_feedback") -> List[str]:
        rules = self._extract_rules(user_text)
        if not rules:
            return []

        for rule in rules:
            self._append_rule_file(rule, source)

            try:
                client, backend = self._get_chroma_client()
                collection = client.get_or_create_collection(name=self.collection_name)
                embedding = self._embed(rule)
                rule_id = hashlib.sha1((rule.lower()).encode("utf-8")).hexdigest()
                collection.upsert(
                    ids=[rule_id],
                    documents=[rule],
                    metadatas=[
                        {
                            "source": source,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "backend": backend,
                        }
                    ],
                    embeddings=[embedding],
                )
            except Exception:
                # JSONL persistence is the safety net.
                continue

        return rules

    def _lexical_retrieve(self, query: str, top_k: int) -> List[str]:
        rules = self._read_rule_file()
        if not rules:
            return []

        tokens = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
        scored: List[Tuple[int, str]] = []
        for rule in rules:
            rule_tokens = set(re.findall(r"[a-zA-Z0-9_]+", rule.lower()))
            score = len(tokens & rule_tokens)
            scored.append((score, rule))
        scored.sort(key=lambda item: item[0], reverse=True)

        picked: List[str] = []
        for _, rule in scored:
            if rule not in picked:
                picked.append(rule)
            if len(picked) >= top_k:
                break
        return picked

    def retrieve(self, query: str, top_k: int | None = None) -> List[str]:
        limit = max(1, top_k or settings.behavior_memory_top_k)
        try:
            client, _ = self._get_chroma_client()
            collection = client.get_or_create_collection(name=self.collection_name)
            embedding = self._embed(query)
            result = collection.query(query_embeddings=[embedding], n_results=limit)
            docs = (result.get("documents") or [[]])[0]
            rows = [str(item).strip() for item in docs if str(item).strip()]
            if rows:
                return rows[:limit]
        except Exception:
            pass

        return self._lexical_retrieve(query, limit)
