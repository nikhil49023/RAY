#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Iterable, List, Tuple

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.config import settings


def _read_sources(root_dir: Path) -> List[Tuple[str, str]]:
    candidates: List[Path] = []
    for relative in ["README.md", "chainlit.md"]:
        path = root_dir / relative
        if path.exists():
            candidates.append(path)

    docs_dir = root_dir / "docs"
    if docs_dir.exists():
        candidates.extend(sorted(docs_dir.rglob("*.md")))

    rows: List[Tuple[str, str]] = []
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if content:
            rows.append((str(path.relative_to(root_dir)), content))
    return rows


def _chunk_text(text: str, max_chars: int = 1200, overlap_chars: int = 180) -> List[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunks: List[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + max_chars)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(0, end - overlap_chars)
    return chunks


def _embedding_endpoints() -> List[str]:
    configured = settings.ollama_base_url.strip().rstrip("/")
    endpoints = [configured] if configured else []
    if "://ollama" in configured:
        endpoints.append(configured.replace("://ollama", "://localhost"))
    return [item for index, item in enumerate(endpoints) if item and item not in endpoints[:index]]


def _embed(text: str) -> List[float]:
    errors: List[str] = []
    for base in _embedding_endpoints():
        for endpoint, payload in [
            ("/api/embeddings", {"model": settings.rag_embedding_model, "prompt": text}),
            ("/api/embed", {"model": settings.rag_embedding_model, "input": text}),
        ]:
            try:
                response = requests.post(base + endpoint, json=payload, timeout=90)
                response.raise_for_status()
                body = response.json()
                embedding = body.get("embedding")
                if not embedding and isinstance(body.get("data"), list) and body["data"]:
                    embedding = body["data"][0].get("embedding")
                if not embedding and isinstance(body.get("embeddings"), list) and body["embeddings"]:
                    first = body["embeddings"][0]
                    if isinstance(first, list):
                        embedding = first
                if embedding:
                    return embedding
                raise RuntimeError("embedding vector missing in Ollama response")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{base}{endpoint}: {type(exc).__name__}: {exc}")
    raise RuntimeError("Failed to fetch embeddings from Ollama. " + " | ".join(errors))


def _collection_names(client: Any) -> List[str]:
    names: List[str] = []
    for row in client.list_collections() or []:
        if isinstance(row, str):
            names.append(row)
            continue
        name = getattr(row, "name", "")
        if name:
            names.append(str(name))
            continue
        if isinstance(row, dict) and row.get("name"):
            names.append(str(row["name"]))
    return names


def _get_chroma_client() -> Tuple[Any, str]:
    if importlib.util.find_spec("chromadb") is None:
        raise RuntimeError("chromadb is not installed. Install requirements-agentic.txt first.")

    chromadb = importlib.import_module("chromadb")
    errors: List[str] = []

    try:
        remote = chromadb.HttpClient(host=settings.rag_chroma_host, port=settings.rag_chroma_port)
        remote.heartbeat()
        return remote, "http"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"http://{settings.rag_chroma_host}:{settings.rag_chroma_port}: {type(exc).__name__}: {exc}")

    local_path = Path(settings.rag_chroma_local_path)
    if not local_path.is_absolute():
        local_path = ROOT_DIR / local_path

    try:
        local = chromadb.PersistentClient(path=str(local_path))
        local.heartbeat()
        return local, "local"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{local_path}: {type(exc).__name__}: {exc}")

    raise RuntimeError("Unable to connect to Chroma. " + " | ".join(errors))


def _batched(items: List[Any], batch_size: int) -> Iterable[List[Any]]:
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local markdown docs into Chroma for RAG.")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the target collection first.")
    parser.add_argument("--batch-size", type=int, default=32, help="Upsert batch size.")
    args = parser.parse_args()

    sources = _read_sources(ROOT_DIR)
    if not sources:
        raise SystemExit("No markdown sources found to index.")

    client, backend = _get_chroma_client()

    if args.reset and settings.rag_collection_name in _collection_names(client):
        client.delete_collection(name=settings.rag_collection_name)

    collection = client.get_or_create_collection(name=settings.rag_collection_name)

    records: List[dict[str, Any]] = []
    for source, text in sources:
        for chunk_index, chunk in enumerate(_chunk_text(text), start=1):
            digest = hashlib.sha1(f"{source}:{chunk_index}:{chunk[:80]}".encode("utf-8")).hexdigest()
            records.append(
                {
                    "id": digest,
                    "source": source,
                    "chunk": chunk,
                    "chunk_index": chunk_index,
                }
            )

    if not records:
        raise SystemExit("No chunks generated for indexing.")

    for batch in _batched(records, max(1, args.batch_size)):
        ids = [item["id"] for item in batch]
        docs = [item["chunk"] for item in batch]
        metas = [{"source": item["source"], "chunk_index": item["chunk_index"]} for item in batch]
        embeddings = [_embed(doc) for doc in docs]
        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    print(
        f"Indexed {len(records)} chunks from {len(sources)} files into '{settings.rag_collection_name}' via {backend} Chroma."
    )


if __name__ == "__main__":
    main()
