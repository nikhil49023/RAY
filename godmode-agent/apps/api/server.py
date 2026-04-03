"""
server.py — FastAPI Backend for RAY God Mode Agent
--------------------------------------------------
Streams responses in Vercel AI SDK Data Stream Protocol.
Adds typed research metadata for documents, charts, sources, and thinking logs.
"""

from __future__ import annotations

import asyncio
import json
import queue
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR.parent / ".env")

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_core.messages import AIMessage, HumanMessage

from services.orchestrator.graph import graph
from services.orchestrator.llm_factory import LLMFactory
from services.orchestrator.runtime import (
    apply_runtime_settings,
    load_user_settings,
    save_user_settings,
)

# ── Data dirs ─────────────────────────────────────────────────────────────── #
DATA_DIR = ROOT_DIR / "data"
THREADS_DIR = DATA_DIR / "threads"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
RESEARCH_DIR = DATA_DIR / "research"
for d in [THREADS_DIR, ARTIFACTS_DIR, RESEARCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="RAY God Mode API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

apply_runtime_settings(load_user_settings())

# ── Helpers ───────────────────────────────────────────────────────────────── #
RENDER_TAG_RE = re.compile(
    r"<(?P<kind>document|canvas):\s*(?P<title>.*?)>(?P<body>.*?)</(?P=kind)>",
    re.IGNORECASE | re.DOTALL,
)
RENDER_CODE_RE = re.compile(
    r"```(?P<lang>chart|mermaid)\s*(?P<body>.*?)```",
    re.IGNORECASE | re.DOTALL,
)

NODE_STATUS = {
    "intent_router": "Routing the request…",
    "planner": "Designing the research plan…",
    "web_rag": "Running DuckDuckGo search…",
    "deep_research": "Running Firecrawl deep research…",
    "composer": "Composing the final response…",
}


def _js(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _load_json_dir(directory: Path) -> List[dict]:
    items = []
    for f in directory.glob("*.json"):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def _extract_render_blocks(text: str) -> List[dict]:
    if not text:
        return []

    blocks: List[dict] = []
    matches: List[dict] = []

    for match in RENDER_TAG_RE.finditer(text):
        matches.append({
            "start": match.start(),
            "kind": match.group("kind").lower(),
            "title": match.group("title").strip() or match.group("kind").title(),
            "body": match.group("body").strip(),
        })

    for match in RENDER_CODE_RE.finditer(text):
        matches.append({
            "start": match.start(),
            "kind": match.group("lang").lower(),
            "title": match.group("lang").title(),
            "body": match.group("body").strip(),
        })

    for item in sorted(matches, key=lambda row: row["start"]):
        if item["kind"] in {"document", "canvas"}:
            blocks.append({
                "type": item["kind"],
                "title": item["title"],
                "content": item["body"],
            })
        elif item["kind"] == "chart":
            chart_payload: Any = item["body"]
            try:
                chart_payload = json.loads(item["body"])
            except Exception:
                pass
            blocks.append({
                "type": "chart",
                "title": chart_payload.get("title", "Chart") if isinstance(chart_payload, dict) else "Chart",
                "chart": chart_payload,
            })
        elif item["kind"] == "mermaid":
            blocks.append({
                "type": "mermaid",
                "title": "Diagram",
                "content": item["body"],
            })

    return blocks


def _primary_document_text(answer: str, blocks: List[dict]) -> str:
    for block in blocks:
        if block.get("type") in {"document", "canvas"}:
            return str(block.get("content", "")).strip()
    return (answer or "").strip()


def _save_generated_artifact(block: dict) -> None:
    if block.get("type") not in {"document", "canvas", "chart"}:
        return

    aid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    content = block.get("content", "")
    if block.get("type") == "chart":
        content = json.dumps(block.get("chart", {}), ensure_ascii=False, indent=2)

    data = {
        "id": aid,
        "title": block.get("title", "Untitled"),
        "content": content,
        "type": block.get("type", "document"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (ARTIFACTS_DIR / f"{aid}.json").write_text(_js(data), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# CHAT  (Vercel AI SDK Data Stream Protocol)
# ══════════════════════════════════════════════════════════════════════════════


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    settings = apply_runtime_settings(load_user_settings())

    messages = body.get("messages", [])
    model = body.get("model", "groq/llama-3.3-70b-versatile")
    mode = body.get("mode", "standard")
    temperature = float(body.get("temperature", settings.get("temperature", 0.1)))

    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break
    if not user_msg:
        user_msg = "Hello"

    initial_state = {
        "messages": [HumanMessage(content=user_msg)],
        "turn_count": 0,
        "evidence": [],
        "artifacts": [],
        "thinking_log": [],
        "node_timings": {},
        "completed_nodes": [],
        "errors": [],
        "agent_mode": mode,
        "selected_model": model,
        "temperature": temperature,
    }

    async def generate():
        q: queue.Queue = queue.Queue()

        def worker():
            try:
                final_state: Dict[str, Any] = {}
                for event in graph.stream(initial_state):
                    for node_id, node_state in event.items():
                        final_state.update(node_state)
                        q.put(("node", node_id, node_state))
                q.put(("done", None, final_state))
            except Exception as exc:
                q.put(("error", None, str(exc)))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            try:
                msg_type, node_id, payload = q.get_nowait()
            except queue.Empty:
                if not thread.is_alive() and q.empty():
                    break
                await asyncio.sleep(0.1)
                continue

            if msg_type == "node":
                status_text = NODE_STATUS.get(node_id or "", f"Running {node_id}…")
                items: List[dict] = [{"status": status_text, "node": node_id}]
                node_logs = payload.get("thinking_log", []) if isinstance(payload, dict) else []
                if node_logs:
                    items.append({"thinking_log_append": node_logs})
                yield "2:" + _js(items) + "\n"

            elif msg_type == "error":
                err = payload or "Unknown error"
                hint = ""
                low_err = err.lower()
                if "401" in err or "403" in err or "invalid_api_key" in low_err:
                    hint = "\n\nCheck your provider or Firecrawl key in Settings."
                elif "rate" in low_err or "429" in err:
                    hint = "\n\nRate limit reached. Wait briefly or switch models."
                elif "connection" in low_err or "refused" in low_err:
                    hint = "\n\nConnection failed. Verify the selected provider and Firecrawl self-host endpoint."
                yield "0:" + _js("Error: " + err + hint) + "\n"
                yield "e:" + _js({"finishReason": "error"}) + "\n"
                yield "d:" + _js({"finishReason": "error"}) + "\n"
                return

            elif msg_type == "done":
                final_state = payload or {}
                answer = final_state.get("answer", "")
                if not answer:
                    for msg in reversed(final_state.get("messages", [])):
                        if isinstance(msg, AIMessage):
                            answer = msg.content
                            break
                if not answer:
                    answer = "No response generated. Try a different model or rephrase your query."

                evidence = final_state.get("evidence", [])
                thinking_log = final_state.get("thinking_log", [])
                render_blocks = _extract_render_blocks(answer)
                research_brief = _primary_document_text(answer, render_blocks)

                chunk_size = 50
                for i in range(0, len(answer), chunk_size):
                    yield "0:" + _js(answer[i:i + chunk_size]) + "\n"
                    await asyncio.sleep(0.006)

                annotations: List[dict] = []
                if evidence:
                    safe_evidence = []
                    for item in evidence[:10]:
                        safe_evidence.append({
                            "source": item.get("source", ""),
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "claim": str(item.get("claim", ""))[:200],
                            "provider": item.get("provider", ""),
                            "relu_score": item.get("relu_score", 0),
                        })
                    annotations.append({"evidence": safe_evidence})

                if thinking_log:
                    annotations.append({"thinking_log": thinking_log})

                if render_blocks:
                    annotations.append({"render_blocks": render_blocks[:12]})

                if final_state.get("plan"):
                    annotations.append({
                        "plan": str(final_state.get("plan", ""))[:2000],
                        "research_level": final_state.get("research_level", "basic"),
                    })

                if annotations:
                    yield "2:" + _js(annotations) + "\n"

                if mode == "research" and (research_brief or evidence):
                    rid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
                    (RESEARCH_DIR / f"{rid}.json").write_text(_js({
                        "id": rid,
                        "query": user_msg[:200],
                        "brief": research_brief[:6000],
                        "sources": [
                            {
                                "source": item.get("source"),
                                "title": item.get("title"),
                                "url": item.get("url"),
                            }
                            for item in evidence[:10]
                        ],
                        "model": model,
                        "plan": str(final_state.get("plan", ""))[:2000],
                        "thinking_log": thinking_log,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }), encoding="utf-8")

                for block in render_blocks:
                    _save_generated_artifact(block)

                yield "e:" + _js({
                    "finishReason": "stop",
                    "usage": {"promptTokens": 0, "completionTokens": 0},
                }) + "\n"
                yield "d:" + _js({
                    "finishReason": "stop",
                    "usage": {"promptTokens": 0, "completionTokens": 0},
                }) + "\n"
                return

        yield "0:" + _js("Processing ended unexpectedly. Please try again.") + "\n"
        yield "e:" + _js({"finishReason": "error"}) + "\n"
        yield "d:" + _js({"finishReason": "error"}) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Vercel-AI-Data-Stream": "v1", "Cache-Control": "no-cache"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/models")
async def list_models():
    apply_runtime_settings(load_user_settings())
    return {"models": LLMFactory.list_models()}


# ══════════════════════════════════════════════════════════════════════════════
# THREADS
# ══════════════════════════════════════════════════════════════════════════════


class ThreadSave(BaseModel):
    title: str = "Untitled"
    messages: List[dict] = []


@app.get("/api/threads")
async def list_threads():
    items = _load_json_dir(THREADS_DIR)
    return {
        "threads": [{
            "id": item["id"],
            "title": item.get("title", "Untitled"),
            "updated_at": item.get("updated_at", ""),
            "message_count": len(item.get("messages", [])),
        } for item in items[:30]]
    }


@app.post("/api/threads")
async def save_thread(body: ThreadSave):
    tid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    data = {
        "id": tid,
        "title": body.title,
        "messages": body.messages,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (THREADS_DIR / f"{tid}.json").write_text(_js(data), encoding="utf-8")
    return {"id": tid}


@app.get("/api/threads/{tid}")
async def get_thread(tid: str):
    f = THREADS_DIR / f"{tid}.json"
    if not f.exists():
        raise HTTPException(404)
    return json.loads(f.read_text(encoding="utf-8"))


@app.delete("/api/threads/{tid}")
async def delete_thread(tid: str):
    f = THREADS_DIR / f"{tid}.json"
    if f.exists():
        f.unlink()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# ARTIFACTS
# ══════════════════════════════════════════════════════════════════════════════


class ArtifactSave(BaseModel):
    title: str
    content: str
    type: str = "document"


@app.get("/api/artifacts")
async def list_artifacts():
    items = _load_json_dir(ARTIFACTS_DIR)
    return {
        "artifacts": [{
            "id": item["id"],
            "title": item.get("title", ""),
            "type": item.get("type", ""),
            "created_at": item.get("created_at", ""),
            "preview": item.get("content", "")[:150],
        } for item in items[:30]]
    }


@app.post("/api/artifacts")
async def save_artifact(body: ArtifactSave):
    aid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    data = {
        "id": aid,
        "title": body.title,
        "content": body.content,
        "type": body.type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (ARTIFACTS_DIR / f"{aid}.json").write_text(_js(data), encoding="utf-8")
    return {"id": aid}


@app.get("/api/artifacts/{aid}")
async def get_artifact(aid: str):
    f = ARTIFACTS_DIR / f"{aid}.json"
    if not f.exists():
        raise HTTPException(404)
    return json.loads(f.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
# RESEARCH
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/research")
async def list_research():
    items = _load_json_dir(RESEARCH_DIR)
    return {
        "sessions": [{
            "id": item["id"],
            "query": item.get("query", ""),
            "model": item.get("model", ""),
            "created_at": item.get("created_at", ""),
            "source_count": len(item.get("sources", [])),
        } for item in items[:30]]
    }


@app.get("/api/research/{rid}")
async def get_research(rid: str):
    f = RESEARCH_DIR / f"{rid}.json"
    if not f.exists():
        raise HTTPException(404)
    return json.loads(f.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/settings")
async def get_settings():
    return apply_runtime_settings(load_user_settings())


@app.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    settings = save_user_settings(data)
    apply_runtime_settings(settings)
    return {"ok": True, "settings": settings}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
