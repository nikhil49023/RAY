"""
server.py — FastAPI Backend for RAY God Mode Agent
--------------------------------------------------
Streams responses in Vercel AI SDK Data Stream Protocol.
Adds typed research metadata for documents, charts, sources, and thinking logs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import queue
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import httpx
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
import unicodedata

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ray.api")

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR.parent / ".env")

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_core.messages import AIMessage, HumanMessage

from core.graph import graph
from core.llm_factory import LLMFactory
from core.runtime import (
    apply_runtime_settings,
    get_agent_runtime_config,
    load_user_settings,
    save_user_settings,
)
from services.agent_backends.codex_cli import stream_codex_cli
from services.memory.semantic_memory import retrieve_semantic_memory
from services.memory.semantic_memory import write_semantic_memory
from services.memory.stores.qdrant_index import QdrantIndex

# ── Data dirs ─────────────────────────────────────────────────────────────── #
DATA_DIR = ROOT_DIR / "data"
THREADS_DIR = DATA_DIR / "threads"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
RESEARCH_DIR = DATA_DIR / "research"
for d in [THREADS_DIR, ARTIFACTS_DIR, RESEARCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

execution_index = QdrantIndex(collection_name="execution_index")

# ── CORS Configuration ───────────────────────────────────────────────────── #
# Environment-based CORS configuration for security
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
).split(",")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]
# Fallback to wildcard only in development mode
if os.getenv("RAY_ENV", "development") == "development" and not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"]

app = FastAPI(
    title="RAY God Mode API",
    description="Multi-model AI assistant with research and reasoning capabilities",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    max_age=3600,  # Cache preflight requests for 1 hour
)
logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")

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

# Maximum limits for safety
MAX_MESSAGE_LENGTH = 50000  # ~50KB per message
MAX_MESSAGES = 100
MAX_TITLE_LENGTH = 500
MAX_CONTENT_LENGTH = 1000000  # ~1MB


def _normalize_resource_id(resource_id: str) -> str:
    normalized = unicodedata.normalize("NFKC", resource_id or "").strip()
    if not normalized or not re.fullmatch(r"[a-zA-Z0-9_-]+", normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid resource ID format"
        )
    return normalized


def _sanitize_id(resource_id: str, directory: Path) -> Path:
    """Safely construct a file path, preventing path traversal attacks."""
    safe_id = _normalize_resource_id(resource_id)
    # Construct path and verify it's within the expected directory
    filepath = directory / f"{safe_id}.json"
    try:
        filepath.resolve().relative_to(directory.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid resource ID"
        )
    return filepath


def _safe_json_load(filepath: Path) -> Optional[dict]:
    """Safely load JSON with size limit and error handling."""
    try:
        if not filepath.exists():
            return None
        if filepath.stat().st_size > MAX_CONTENT_LENGTH:
            logger.warning(f"File too large: {filepath}")
            return None
        content = filepath.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {filepath}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None


def _js(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _to_langchain_messages(messages: List[dict]) -> List[HumanMessage | AIMessage]:
    converted: List[HumanMessage | AIMessage] = []
    for item in messages:
        role = str(item.get("role", "")).lower()
        content = _message_content_to_text(item.get("content", ""))
        if not content.strip():
            continue
        if role == "assistant":
            converted.append(AIMessage(content=content))
        elif role == "user":
            converted.append(HumanMessage(content=content))
    return converted


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
        matches.append(
            {
                "start": match.start(),
                "kind": match.group("kind").lower(),
                "title": match.group("title").strip() or match.group("kind").title(),
                "body": match.group("body").strip(),
            }
        )

    for match in RENDER_CODE_RE.finditer(text):
        matches.append(
            {
                "start": match.start(),
                "kind": match.group("lang").lower(),
                "title": match.group("lang").title(),
                "body": match.group("body").strip(),
            }
        )

    for item in sorted(matches, key=lambda row: row["start"]):
        if item["kind"] in {"document", "canvas"}:
            blocks.append(
                {
                    "type": item["kind"],
                    "title": item["title"],
                    "content": item["body"],
                }
            )
        elif item["kind"] == "chart":
            chart_payload: Any = item["body"]
            try:
                chart_payload = json.loads(item["body"])
            except Exception:
                pass
            blocks.append(
                {
                    "type": "chart",
                    "title": chart_payload.get("title", "Chart")
                    if isinstance(chart_payload, dict)
                    else "Chart",
                    "chart": chart_payload,
                }
            )
        elif item["kind"] == "mermaid":
            blocks.append(
                {
                    "type": "mermaid",
                    "title": "Diagram",
                    "content": item["body"],
                }
            )

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


def _codex_proxy_payload(raw: bytes) -> bytes:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        return raw

    payload.pop("web_search_options", None)
    payload.pop("tools", None)
    payload.pop("tool_choice", None)
    payload.pop("parallel_tool_calls", None)
    payload.pop("max_tool_calls", None)
    payload.pop("include", None)
    payload.pop("prompt_cache_key", None)
    payload.pop("store", None)
    reasoning = payload.get("reasoning")
    if isinstance(reasoning, dict):
        reasoning.pop("summary", None)
        if not reasoning:
            payload.pop("reasoning", None)

    # Codex sends a very large built-in instruction block that pushes Groq's
    # request size over the model TPM/request budget. Keep a concise system
    # instruction and rely on the actual user input for the turn content.
    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        payload["instructions"] = (
            "You are Codex running behind the RAY chat UI. "
            "Answer the latest user request clearly and concisely."
        )

    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _runtime_model_entries(settings: Dict[str, Any]) -> List[dict]:
    runtime = get_agent_runtime_config(settings)
    if runtime.get("backend") != "codex_cli":
        return LLMFactory.list_model_entries()

    model_id = runtime.get("codex_model", "openai/gpt-oss-20b")
    return [
        {
            "id": model_id,
            "label": f"Codex via Groq ({model_id})",
            "provider": "Codex CLI",
            "specialty": "CLI agent runtime",
            "description": "Codex CLI running locally with Groq as its OpenAI-compatible model provider.",
            "features": ["Tools", "CLI Agent", "Workspace", "Groq"],
            "is_default": True,
        }
    ]


def _resolve_chat_model(requested_model: str, runtime: Dict[str, Any]) -> str:
    requested = str(requested_model or "").strip()
    if runtime.get("backend") == "codex_cli":
        configured = str(runtime.get("codex_model") or "").strip()
        return configured or "openai/gpt-oss-20b"
    return requested or "groq/llama-3.3-70b-versatile"


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ══════════════════════════════════════════════════════════════════════════════


class MessageContent(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()


class FeedbackRequest(BaseModel):
    text: str
    type: str = "correction"

class ChatRequest(BaseModel):
    messages: List[MessageContent] = Field(
        default_factory=list, max_length=MAX_MESSAGES
    )
    model: str = Field(default="groq/llama-3.3-70b-versatile")
    mode: str = Field(default="standard", pattern="^(standard|research|reasoning)$")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    visualsEnabled: bool = Field(default=False)
    sessionId: Optional[str] = Field(default=None, max_length=MAX_TITLE_LENGTH)


class ThreadSave(BaseModel):
    id: Optional[str] = Field(default=None, max_length=MAX_TITLE_LENGTH)
    title: str = Field(default="Untitled", max_length=MAX_TITLE_LENGTH)
    messages: List[dict] = Field(default_factory=list, max_length=MAX_MESSAGES)


class ArtifactSave(BaseModel):
    title: str = Field(..., max_length=MAX_TITLE_LENGTH)
    content: str = Field(..., max_length=MAX_CONTENT_LENGTH)
    type: str = Field(default="document", pattern="^(document|canvas|chart|mermaid)$")


class IllustrationRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    style: str = Field(default="cinematic 3d educational render", max_length=200)
    aspectRatio: str = Field(default="16:9", pattern="^(16:9|4:3|1:1|3:2)$")


def _illustration_dimensions(aspect_ratio: str) -> tuple[int, int]:
    return {
        "16:9": (1344, 768),
        "4:3": (1152, 896),
        "1:1": (1024, 1024),
        "3:2": (1216, 832),
    }.get(aspect_ratio, (1344, 768))


def _fallback_illustration_url(prompt: str, style: str, aspect_ratio: str) -> str:
    width, height = _illustration_dimensions(aspect_ratio)
    prompt_text = quote(
        f"{prompt.strip()}. Style: {style.strip()}. Premium polished educational illustration, clean composition, no text overlays."
    )
    return (
        f"https://image.pollinations.ai/prompt/{prompt_text}"
        f"?width={width}&height={height}&nologo=true&model=flux"
    )


async def _generate_huggingface_illustration(
    prompt: str, style: str, aspect_ratio: str
) -> str:
    token = (os.getenv("HUGGINGFACE_API_TOKEN") or "").strip()
    model = (
        os.getenv("HUGGINGFACE_IMAGE_MODEL") or "black-forest-labs/FLUX.1-schnell"
    ).strip()
    if not token:
        return _fallback_illustration_url(prompt, style, aspect_ratio)

    width, height = _illustration_dimensions(aspect_ratio)
    full_prompt = (
        f"{prompt.strip()}. "
        f"Style: {style.strip()}. "
        "Create a beautiful, understandable educational illustration with strong visual hierarchy, "
        "clear subject separation, premium lighting, elegant materials, readable structure, and focused composition. "
        "Avoid flat infographic look, avoid clutter, avoid tiny details, avoid text overlays, avoid watermarks."
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/png",
    }
    payload = {
        "inputs": full_prompt,
        "parameters": {
            "width": width,
            "height": height,
            "guidance_scale": 6.0,
            "num_inference_steps": 6,
        },
    }

    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    timeout = httpx.Timeout(120.0, connect=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        logger.warning(
            "Hugging Face illustration failed with status %s: %s. Falling back.",
            response.status_code,
            response.text[:400],
        )
        return _fallback_illustration_url(prompt, style, aspect_ratio)
    if "image/" not in content_type:
        logger.warning(
            "Hugging Face illustration returned non-image content type %s. Falling back.",
            content_type,
        )
        return _fallback_illustration_url(prompt, style, aspect_ratio)

    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


# ══════════════════════════════════════════════════════════════════════════════
# CHAT  (Vercel AI SDK Data Stream Protocol)
# ══════════════════════════════════════════════════════════════════════════════


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body",
        )

    # Validate request
    try:
        chat_req = ChatRequest(**body)
        messages = [{"role": m.role, "content": m.content} for m in chat_req.messages]
        model = chat_req.model
        mode = chat_req.mode
        temperature = chat_req.temperature
    except Exception as e:
        logger.warning(f"Invalid chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request parameters: {str(e)}",
        )

    settings = apply_runtime_settings(load_user_settings())
    runtime = get_agent_runtime_config(settings)
    model = _resolve_chat_model(model, runtime)

    conversation = _to_langchain_messages(
        messages if isinstance(messages, list) else []
    )
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = _message_content_to_text(m.get("content", ""))
            break
    if not user_msg:
        user_msg = "Hello"
    if not conversation:
        conversation = [HumanMessage(content=user_msg)]

    user_turns = sum(1 for msg in conversation if isinstance(msg, HumanMessage))
    retrieved_memory = retrieve_semantic_memory(
        user_msg, top_k=10 if mode == "research" else 5
    )

    initial_state = {
        "messages": conversation,
        "turn_count": max(user_turns - 1, 0),
        "memory_context": retrieved_memory.get("memory_context", ""),
        "memory_hits": retrieved_memory.get("memory_hits", []),
        "behavioral_memories": retrieved_memory.get("behavioral_memories", []),
        "memory_writes": [],
        "session_id": chat_req.sessionId or "",
        "evidence": [],
        "scraped_data": [],
        "firecrawl_summary": "",
        "artifacts": [],
        "thinking_log": [],
        "node_timings": {},
        "completed_nodes": [],
        "errors": [],
        "agent_mode": mode,
        "selected_model": model,
        "temperature": temperature,
        "visuals_enabled": bool(
            body.get(
                "visualsEnabled",
                settings.get("ui", {}).get("renderVisualsInline", False),
            )
        ),
    }

    async def generate():
        q: queue.Queue = queue.Queue()
        request_id = uuid.uuid4().hex[:8]
        backend = runtime.get("backend", "langgraph")
        logger.info(
            f"[{request_id}] Starting chat request - backend={backend}, model={model}, mode={mode}"
        )

        def worker():
            if backend == "codex_cli":
                try:
                    for event in stream_codex_cli(
                        messages=messages,
                        runtime=runtime,
                        mode=mode,
                        visuals_enabled=bool(initial_state.get("visuals_enabled")),
                        memory_context=str(initial_state.get("memory_context", "")),
                        behavioral_memories=list(
                            initial_state.get("behavioral_memories", [])
                        ),
                        model=model,
                        workdir=ROOT_DIR,
                    ):
                        event_type = event.get("event")
                        if event_type == "status":
                            q.put(("status", "codex_cli", event))
                        elif event_type == "log":
                            q.put(("log", "codex_cli", event))
                        elif event_type == "error":
                            q.put(
                                (
                                    "error",
                                    None,
                                    event.get("error", "Codex execution failed."),
                                )
                            )
                            return
                        elif event_type == "done":
                            q.put(("done", None, event))
                            logger.info(
                                f"[{request_id}] Codex CLI execution completed successfully"
                            )
                            return

                    q.put(("error", None, "Codex execution ended unexpectedly."))
                except Exception as exc:
                    logger.error(f"[{request_id}] Codex CLI execution error: {exc}")
                    q.put(("error", None, str(exc)))
                return

            try:
                final_state: Dict[str, Any] = {}
                for event in graph.stream(initial_state):
                    for node_id, node_state in event.items():
                        final_state.update(node_state)
                        q.put(("node", node_id, node_state))
                q.put(("done", None, final_state))
                logger.info(f"[{request_id}] Graph execution completed successfully")
            except Exception as exc:
                logger.error(f"[{request_id}] Graph execution error: {exc}")
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
                node_logs = (
                    payload.get("thinking_log", []) if isinstance(payload, dict) else []
                )
                if node_logs:
                    items.append({"thinking_log_append": node_logs})
                yield "2:" + _js(items) + "\n"

            elif msg_type == "status":
                status_text = str(payload.get("status", "Codex is working…"))
                yield "2:" + _js([{"status": status_text, "node": node_id}]) + "\n"

            elif msg_type == "log":
                node_logs = (
                    payload.get("thinking_log", []) if isinstance(payload, dict) else []
                )
                if node_logs:
                    yield "2:" + _js([{"thinking_log_append": node_logs}]) + "\n"

            elif msg_type == "error":
                err = payload or "Unknown error"
                hint = ""
                low_err = err.lower()
                logger.error(f"[{request_id}] Stream error: {err}")

                # Provide actionable hints based on error type
                if "401" in err or "403" in err or "invalid_api_key" in low_err:
                    hint = "\n\n**Solution:** Check your API key in Settings. Ensure the key is valid and has proper permissions."
                elif "rate" in low_err or "429" in err:
                    hint = "\n\n**Solution:** Rate limit reached. Wait 60 seconds or switch to a different model."
                elif (
                    "connection" in low_err
                    or "refused" in low_err
                    or "timeout" in low_err
                ):
                    hint = "\n\n**Solution:** Connection failed. Check if the service is running:\n- For Ollama: `ollama serve`\n- For Firecrawl: verify the self-hosted endpoint"
                elif "model" in low_err and (
                    "not found" in low_err or "unavailable" in low_err
                ):
                    hint = "\n\n**Solution:** Model not available. Select a different model from the dropdown."
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
                    logger.warning(f"[{request_id}] Empty response generated")

                evidence = final_state.get("evidence", [])
                thinking_log = final_state.get("thinking_log", [])
                render_blocks = _extract_render_blocks(answer)
                research_brief = _primary_document_text(answer, render_blocks)

                logger.info(
                    f"[{request_id}] Response ready - evidence={len(evidence)}, blocks={len(render_blocks)}"
                )

                chunk_size = 50
                for i in range(0, len(answer), chunk_size):
                    yield "0:" + _js(answer[i : i + chunk_size]) + "\n"
                    await asyncio.sleep(0.006)

                annotations: List[dict] = []
                if evidence:
                    safe_evidence = []
                    for item in evidence[:10]:
                        safe_evidence.append(
                            {
                                "source": item.get("source", ""),
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "claim": str(item.get("claim", ""))[:200],
                                "provider": item.get("provider", ""),
                                "relu_score": item.get("relu_score", 0),
                            }
                        )
                    annotations.append({"evidence": safe_evidence})

                if thinking_log:
                    annotations.append({"thinking_log": thinking_log})

                if render_blocks:
                    annotations.append({"render_blocks": render_blocks[:12]})

                if final_state.get("plan"):
                    annotations.append(
                        {
                            "plan": str(final_state.get("plan", ""))[:2000],
                            "research_level": final_state.get(
                                "research_level", "basic"
                            ),
                        }
                    )

                if final_state.get("memory_hits"):
                    annotations.append(
                        {"memory_hits": final_state.get("memory_hits", [])[:5]}
                    )

                if annotations:
                    yield "2:" + _js(annotations) + "\n"

                if mode == "research" and (research_brief or evidence):
                    rid = (
                        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
                        + uuid.uuid4().hex[:6]
                    )
                    (RESEARCH_DIR / f"{rid}.json").write_text(
                        _js(
                            {
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
                            }
                        ),
                        encoding="utf-8",
                    )

                for block in render_blocks:
                    _save_generated_artifact(block)

                yield (
                    "e:"
                    + _js(
                        {
                            "finishReason": "stop",
                            "usage": {"promptTokens": 0, "completionTokens": 0},
                        }
                    )
                    + "\n"
                )
                yield (
                    "d:"
                    + _js(
                        {
                            "finishReason": "stop",
                            "usage": {"promptTokens": 0, "completionTokens": 0},
                        }
                    )
                    + "\n"
                )
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
    settings = apply_runtime_settings(load_user_settings())
    models = _runtime_model_entries(settings)
    return {
        "models": models,
        "defaultModel": next(
            (item["id"] for item in models if item.get("is_default")),
            models[0]["id"] if models else None,
        ),
        "singleModelMode": len(models) <= 1,
    }


@app.get("/api/codex-openai/v1/models")
async def codex_proxy_models():
    return {
        "object": "list",
        "data": [
            {"id": "openai/gpt-oss-20b", "object": "model", "owned_by": "groq"},
            {"id": "openai/gpt-oss-120b", "object": "model", "owned_by": "groq"},
        ],
    }


@app.post("/api/codex-openai/v1/responses")
async def codex_proxy_responses(request: Request):
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GROQ_API_KEY is not configured on the server.",
        )

    body = await request.body()
    try:
        filtered_body = _codex_proxy_payload(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid responses payload: {exc}",
        )

    target_url = "https://api.groq.com/openai/v1/responses"
    content_type = request.headers.get("content-type", "application/json")

    async def generate():
        timeout = httpx.Timeout(120.0, connect=30.0)
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": content_type,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", target_url, headers=headers, content=filtered_body
            ) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    try:
                        payload_preview = json.loads(filtered_body.decode("utf-8"))
                    except Exception:
                        payload_preview = {
                            "raw": filtered_body.decode("utf-8", errors="replace")[
                                :2000
                            ]
                        }
                    if isinstance(payload_preview, dict):
                        preview = dict(payload_preview)
                        instructions = preview.get("instructions")
                        if isinstance(instructions, str):
                            preview["instructions"] = instructions[:240]
                        preview["input"] = (
                            f"<{len(preview.get('input', []))} input items>"
                        )
                        payload_preview = preview
                    logger.error(
                        "Codex proxy upstream error %s payload=%s response=%s",
                        response.status_code,
                        payload_preview,
                        error_body.decode("utf-8", errors="replace")[:4000],
                    )
                    yield error_body
                    return
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

    return StreamingResponse(
        generate(),
        media_type=request.headers.get("accept", "text/event-stream"),
        headers={"Cache-Control": "no-cache"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# THREADS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/threads")
async def list_threads():
    items = _load_json_dir(THREADS_DIR)
    return {
        "threads": [
            {
                "id": item["id"],
                "title": item.get("title", "Untitled"),
                "updated_at": item.get("updated_at", ""),
                "message_count": len(item.get("messages", [])),
            }
            for item in items[:30]
        ]
    }


@app.post("/api/threads")
async def save_thread(body: ThreadSave):
    tid = (
        _normalize_resource_id(body.id)
        if body.id
        else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:6]
    )
    existing = _safe_json_load(THREADS_DIR / f"{tid}.json") if body.id else None
    data = {
        "id": tid,
        "title": body.title[:MAX_TITLE_LENGTH],
        "messages": body.messages[:MAX_MESSAGES],
        "created_at": (existing or {}).get(
            "created_at", datetime.now(timezone.utc).isoformat()
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    filepath = THREADS_DIR / f"{tid}.json"
    filepath.write_text(_js(data), encoding="utf-8")
    user_text = "\n\n".join(
        str(item.get("content", ""))
        for item in body.messages
        if item.get("role") == "user"
    )
    assistant_text = "\n\n".join(
        str(item.get("content", ""))
        for item in body.messages
        if item.get("role") == "assistant"
    )
    write_semantic_memory(
        user_input=user_text,
        assistant_output=assistant_text,
        session_id=tid,
        source="thread_archive",
    )
    logger.info(f"Saved thread: {tid}")
    return {"id": tid}


@app.get("/api/threads/{tid}")
async def get_thread(tid: str):
    try:
        filepath = _sanitize_id(tid, THREADS_DIR)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )

    data = _safe_json_load(filepath)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return data


@app.delete("/api/threads/{tid}")
async def delete_thread(tid: str):
    try:
        filepath = _sanitize_id(tid, THREADS_DIR)
    except HTTPException:
        return {"ok": True}  # Idempotent delete

    if filepath.exists():
        filepath.unlink()
        try:
            execution_index.delete_by_field("session_id", tid)
        except Exception as exc:
            logger.warning(
                f"Failed to delete archived semantic memory for thread {tid}: {exc}"
            )
        logger.info(f"Deleted thread: {tid}")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# ARTIFACTS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/artifacts")
async def list_artifacts():
    items = _load_json_dir(ARTIFACTS_DIR)
    return {
        "artifacts": [
            {
                "id": item["id"],
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "created_at": item.get("created_at", ""),
                "preview": item.get("content", "")[:150],
            }
            for item in items[:30]
        ]
    }


@app.post("/api/artifacts")
async def save_artifact(body: ArtifactSave):
    aid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    data = {
        "id": aid,
        "title": body.title[:MAX_TITLE_LENGTH],
        "content": body.content[:MAX_CONTENT_LENGTH],
        "type": body.type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    filepath = ARTIFACTS_DIR / f"{aid}.json"
    filepath.write_text(_js(data), encoding="utf-8")
    logger.info(f"Saved artifact: {aid}")
    return {"id": aid}


@app.get("/api/artifacts/{aid}")
async def get_artifact(aid: str):
    try:
        filepath = _sanitize_id(aid, ARTIFACTS_DIR)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found"
        )

    data = _safe_json_load(filepath)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found"
        )
    return data


# ══════════════════════════════════════════════════════════════════════════════
# RESEARCH
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/research")
async def list_research():
    items = _load_json_dir(RESEARCH_DIR)
    return {
        "sessions": [
            {
                "id": item["id"],
                "query": item.get("query", ""),
                "model": item.get("model", ""),
                "created_at": item.get("created_at", ""),
                "source_count": len(item.get("sources", [])),
            }
            for item in items[:30]
        ]
    }


@app.get("/api/research/{rid}")
async def get_research(rid: str):
    try:
        filepath = _sanitize_id(rid, RESEARCH_DIR)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Research session not found"
        )

    data = _safe_json_load(filepath)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Research session not found"
        )
    return data


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/settings")
async def get_settings():
    return apply_runtime_settings(load_user_settings())


@app.post("/api/settings")
async def save_settings(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body",
        )

    # Validate settings structure
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Settings must be an object"
        )

    # Sanitize sensitive data in logs
    safe_data = {k: v for k, v in data.items() if k not in ("apiKeys",)}
    logger.info(f"Updating settings: {safe_data}")

    settings = save_user_settings(data)
    apply_runtime_settings(settings)
    return {"ok": True, "settings": settings}


@app.post("/api/illustrations")
async def generate_illustration(body: IllustrationRequest):
    image_url = await _generate_huggingface_illustration(
        prompt=body.prompt,
        style=body.style,
        aspect_ratio=body.aspectRatio,
    )
    return {
        "imageUrl": image_url,
        "model": (
            os.getenv("HUGGINGFACE_IMAGE_MODEL") or "black-forest-labs/FLUX.1-schnell"
        ).strip(),
        "aspectRatio": body.aspectRatio,
    }


@app.post("/api/feedback")
async def save_feedback(body: FeedbackRequest):
    try:
        from services.memory.ollama_embedder import embedder
        from services.memory.stores.qdrant_index import QdrantIndex
        import time
        behavior_index = QdrantIndex(collection_name="behavior_index")
        
        vector = embedder.embed_query(body.text)
        point_id = int(time.time_ns() % 9_223_372_036_854_775_000)
        behavior_index.upsert(
            ids=[point_id],
            vectors=[vector],
            payloads=[{"rule": body.text, "type": body.type, "timestamp": time.time()}],
        )
        return {"status": "success", "message": "Feedback saved to behavior_index"}
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills")
async def list_skills():
    try:
        from core.skills import AVAILABLE_SKILLS
        return {
            "skills": [
                {"name": s.name, "description": s.description}
                for s in AVAILABLE_SKILLS
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class SkillExecutionRequest(BaseModel):
    name: str
    prompt: str
    params: dict = {}

@app.post("/api/skills/execute")
async def execute_skill(body: SkillExecutionRequest):
    try:
        from core.skills import get_skill
        skill = get_skill(body.name)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        result = skill.execute(prompt=body.prompt, **body.params)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Failed to execute skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
