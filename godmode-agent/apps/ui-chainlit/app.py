"""
app.py — God Mode Agent · Chainlit UI
---------------------------------------
Full-featured chat interface with:
- Manual brain selection (Sarvam, Groq, Ollama, OpenRouter)
- Mode selection (Standard, Research, Reasoning)
- Chat history persistence with thread resume
- Artifact saving and browsing
- Research savings with search
- Settings panel with temperature control
- Canvas document rendering (side-pane)
- Mermaid diagram support (in-chat)
- Dark premium theme via custom CSS
"""

from __future__ import annotations

import asyncio
import re
import time
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chainlit as cl
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────── #

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.orchestrator.graph import graph
from services.orchestrator.llm_factory import LLMFactory
from langchain_core.messages import HumanMessage, AIMessage

# ── Data Directories ─────────────────────────────────────────────────────── #

DATA_DIR = ROOT_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
HISTORY_FILE = MEMORY_DIR / "chainlit_history.jsonl"
THREADS_DIR = DATA_DIR / "threads"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
RESEARCH_DIR = DATA_DIR / "research"
SETTINGS_FILE = DATA_DIR / "user_settings.json"

for d in [MEMORY_DIR, THREADS_DIR, ARTIFACTS_DIR, RESEARCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE LAYER
# ══════════════════════════════════════════════════════════════════════════════

def _save_message(role: str, content: str, thread_id: str = "default"):
    """Save a message to the chat history JSONL file."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content[:4000],
            "thread_id": thread_id,
        }, ensure_ascii=True) + "\n")


def _save_thread(thread_id: str, title: str, messages: List[dict]):
    """Save a conversation thread to disk."""
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    thread_file = THREADS_DIR / f"{thread_id}.json"
    data = {
        "id": thread_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": messages,
    }
    # Update if exists, create if not
    if thread_file.exists():
        existing = json.loads(thread_file.read_text())
        data["created_at"] = existing.get("created_at", data["created_at"])
        data["messages"] = existing.get("messages", []) + messages
    thread_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_threads() -> List[dict]:
    """Load all threads sorted by last update."""
    threads = []
    for f in THREADS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            threads.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sorted(threads, key=lambda x: x["updated_at"], reverse=True)


def _load_thread(thread_id: str) -> Optional[dict]:
    """Load a specific thread by ID."""
    thread_file = THREADS_DIR / f"{thread_id}.json"
    if thread_file.exists():
        return json.loads(thread_file.read_text())
    return None


def _save_artifact(title: str, content: str, artifact_type: str = "document"):
    """Save an artifact to the artifacts directory."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    artifact_file = ARTIFACTS_DIR / f"{artifact_id}.json"
    artifact_file.write_text(json.dumps({
        "id": artifact_id,
        "title": title,
        "content": content,
        "type": artifact_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False))
    return artifact_id


def _load_artifacts() -> List[dict]:
    """Load all saved artifacts."""
    artifacts = []
    for f in ARTIFACTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            artifacts.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "type": data.get("type", "document"),
                "created_at": data.get("created_at", ""),
                "preview": data.get("content", "")[:200],
            })
        except Exception:
            continue
    return sorted(artifacts, key=lambda x: x["created_at"], reverse=True)


def _load_artifact(artifact_id: str) -> Optional[dict]:
    """Load a specific artifact."""
    for f in ARTIFACTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("id") == artifact_id:
                return data
        except Exception:
            continue
    return None


def _save_research(query: str, brief: str, sources: List[dict], model: str):
    """Save a research session."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    research_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    research_file = RESEARCH_DIR / f"{research_id}.json"
    research_file.write_text(json.dumps({
        "id": research_id,
        "query": query,
        "brief": brief,
        "sources": sources,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False))
    return research_id


def _load_research_sessions() -> List[dict]:
    """Load all research sessions."""
    sessions = []
    for f in RESEARCH_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "id": data["id"],
                "query": data.get("query", ""),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", ""),
                "source_count": len(data.get("sources", [])),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda x: x["created_at"], reverse=True)


def _load_research(research_id: str) -> Optional[dict]:
    """Load a specific research session."""
    for f in RESEARCH_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("id") == research_id:
                return data
        except Exception:
            continue
    return None


def _load_settings() -> dict:
    """Load user settings from disk."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {
        "temperature": 0.1,
        "max_tokens": None,
        "system_prompt": "",
        "auto_save_research": True,
        "auto_save_artifacts": True,
    }


def _save_settings(settings: dict):
    """Save user settings to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


# ── Session stats ─────────────────────────────────────────────────────────── #

def _stats() -> Dict[str, Any]:
    return cl.user_session.get("stats", {
        "turns": 0, "tokens": 0, "sources": 0,
        "start": time.time(),
    })


def _bump_stats(evidence_count: int):
    s = _stats()
    s["turns"] += 1
    s["sources"] += evidence_count
    cl.user_session.set("stats", s)


# ══════════════════════════════════════════════════════════════════════════════
# LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════════

@cl.on_chat_start
async def start():
    # Generate thread ID
    thread_id = str(uuid.uuid4())
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("thread_messages", [])

    # Load saved settings
    saved = _load_settings()

    # Get model list from factory
    models = LLMFactory.list_models()
    model_ids = list(models.keys())
    default_model = model_ids[0] if model_ids else "groq/llama-3.3-70b-versatile"

    settings = cl.ChatSettings([
        cl.input_widget.Select(
            id="Brain",
            label="🧠 Model",
            values=model_ids,
            initial_value=default_model,
        ),
        cl.input_widget.Select(
            id="Mode",
            label="⚡ Mode",
            values=["standard", "research", "reasoning"],
            initial_value="standard",
        ),
        cl.input_widget.Slider(
            id="Temperature",
            label="🌡️ Temperature",
            min=0.0,
            max=1.0,
            step=0.05,
            initial=saved.get("temperature", 0.1),
        ),
        cl.input_widget.TextInput(
            id="SystemPrompt",
            label="📝 System Prompt Override",
            initial=saved.get("system_prompt", ""),
            placeholder="Optional custom instructions...",
        ),
        cl.input_widget.TextInput(
            id="SarvamKey",
            label="🔑 Sarvam API Key",
            initial=os.getenv("SARVAM_API_KEY", ""),
        ),
        cl.input_widget.TextInput(
            id="GroqKey",
            label="🔑 Groq API Key",
            initial=os.getenv("GROQ_API_KEY", ""),
        ),
        cl.input_widget.TextInput(
            id="OpenRouterKey",
            label="🔑 OpenRouter API Key",
            initial=os.getenv("OPENROUTER_API_KEY", ""),
        ),
    ])
    await settings.send()

    cl.user_session.set("brain", default_model)
    cl.user_session.set("mode", "standard")
    cl.user_session.set("temperature", saved.get("temperature", 0.1))
    cl.user_session.set("system_prompt", saved.get("system_prompt", ""))
    cl.user_session.set("stats", {
        "turns": 0, "tokens": 0, "sources": 0, "start": time.time(),
    })

    # Build welcome message with model info
    model_name = models.get(default_model, default_model)
    await cl.Message(content=(
        "## ⚡ RAY God Mode\n"
        "Research assistant ready.\n\n"
        f"**Active Model:** `{model_name}`\n"
        f"**Mode:** Standard\n\n"
        "| Command | Action |\n"
        "|---------|--------|\n"
        "| `/models` | List available models |\n"
        "| `/history` | Show previous conversations |\n"
        "| `/artifacts` | Browse saved artifacts |\n"
        "| `/research` | Browse saved research |\n"
        "| `/settings` | View current settings |\n"
        "| `/save` | Save current conversation |\n"
        "| `/stats` | Session statistics |\n\n"
        "| Mode | Behaviour |\n"
        "|------|----------|\n"
        "| Standard | DuckDuckGo search + AI synthesis |\n"
        "| Research | Deep Firecrawl crawling + extensive search |\n"
        "| Reasoning | Pure AI thinking, no web search |\n\n"
        "*Select your model and mode from ⚙️ Settings. Diagrams render in-chat. Long documents open in the side pane.*"
    )).send()


@cl.on_settings_update
async def on_settings(settings: dict):
    if settings.get("SarvamKey"):
        os.environ["SARVAM_API_KEY"] = settings["SarvamKey"]
    if settings.get("GroqKey"):
        os.environ["GROQ_API_KEY"] = settings["GroqKey"]
    if settings.get("OpenRouterKey"):
        os.environ["OPENROUTER_API_KEY"] = settings["OpenRouterKey"]

    brain = settings.get("Brain", "groq/llama-3.3-70b-versatile")
    mode = settings.get("Mode", "standard")
    temperature = settings.get("Temperature", 0.1)
    system_prompt = settings.get("SystemPrompt", "")

    cl.user_session.set("brain", brain)
    cl.user_session.set("mode", mode)
    cl.user_session.set("temperature", temperature)
    cl.user_session.set("system_prompt", system_prompt)

    # Save settings to disk
    _save_settings({
        "temperature": temperature,
        "system_prompt": system_prompt,
        "auto_save_research": True,
        "auto_save_artifacts": True,
    })

    models = LLMFactory.list_models()
    model_name = models.get(brain, brain)

    await cl.Message(content=(
        f"### ✅ Settings Updated\n"
        f"- **Model:** `{model_name}`\n"
        f"- **Mode:** {mode.title()}\n"
        f"- **Temperature:** {temperature}\n"
        + (f"- **System Prompt:** {system_prompt[:80]}...\n" if system_prompt else "")
    )).send()


# ══════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def _handle_command(query: str) -> bool:
    """Handle slash commands. Returns True if a command was handled."""
    cmd = query.lower().strip()

    # ── /models ───────────────────────────────────────────────────────────
    if cmd == "/models":
        models = LLMFactory.list_models()
        current = cl.user_session.get("brain", "")
        lines = ["### 🧠 Available Models\n"]
        for model_id, label in models.items():
            marker = " ◄ **active**" if model_id == current else ""
            lines.append(f"- `{model_id}` — {label}{marker}")
        lines.append("\n*Switch via ⚙️ Settings or type `/use <model_id>`*")
        await cl.Message(content="\n".join(lines)).send()
        return True

    # ── /use <model_id> ──────────────────────────────────────────────────
    if cmd.startswith("/use "):
        model_id = query[5:].strip()
        models = LLMFactory.list_models()
        if model_id in models:
            cl.user_session.set("brain", model_id)
            await cl.Message(content=f"✅ Switched to **{models[model_id]}**").send()
        else:
            await cl.Message(content=f"❌ Unknown model `{model_id}`. Type `/models` to see available models.").send()
        return True

    # ── /history ──────────────────────────────────────────────────────────
    if cmd == "/history":
        threads = _load_threads()
        if not threads:
            await cl.Message(content="📂 No saved conversations yet. Use `/save` to save the current chat.").send()
            return True

        lines = ["### 📂 Previous Conversations\n"]
        for i, t in enumerate(threads[:15], 1):
            ts = t["updated_at"][:16].replace("T", " ") if t["updated_at"] else "?"
            lines.append(f"**{i}.** {t['title']} — {t['message_count']} msgs — `{ts}`")
            lines.append(f"   → `/load {t['id'][:8]}`")
        lines.append("\n*Use `/load <id>` to resume a conversation*")
        await cl.Message(content="\n".join(lines)).send()
        return True

    # ── /load <thread_id> ────────────────────────────────────────────────
    if cmd.startswith("/load "):
        partial_id = query[6:].strip()
        threads = _load_threads()
        match = None
        for t in threads:
            if t["id"].startswith(partial_id):
                match = _load_thread(t["id"])
                break
        if match:
            # Display loaded thread
            lines = [f"### 📜 Loaded: {match.get('title', 'Untitled')}\n"]
            for msg in match.get("messages", [])[-10:]:
                role_icon = "👤" if msg["role"] == "user" else "🤖"
                content_preview = msg["content"][:300]
                lines.append(f"{role_icon} **{msg['role'].title()}:** {content_preview}\n")
            lines.append("---\n*Conversation loaded. Continue chatting below.*")
            await cl.Message(content="\n".join(lines)).send()

            # Restore session context
            cl.user_session.set("session_summary", match.get("summary", ""))
            cl.user_session.set("thread_id", match["id"])
        else:
            await cl.Message(content=f"❌ No conversation found matching `{partial_id}`").send()
        return True

    # ── /save ─────────────────────────────────────────────────────────────
    if cmd == "/save" or cmd.startswith("/save "):
        title = query[6:].strip() if cmd.startswith("/save ") else None
        thread_id = cl.user_session.get("thread_id", str(uuid.uuid4()))
        thread_messages = cl.user_session.get("thread_messages", [])

        if not thread_messages:
            await cl.Message(content="📝 Nothing to save yet — start chatting first!").send()
            return True

        if not title:
            # Auto-generate title from first message
            title = thread_messages[0]["content"][:60] + "..." if thread_messages else "Untitled"

        _save_thread(thread_id, title, thread_messages)
        await cl.Message(content=f"💾 Conversation saved as **{title}**\nID: `{thread_id[:8]}`").send()
        return True

    # ── /artifacts ────────────────────────────────────────────────────────
    if cmd == "/artifacts":
        artifacts = _load_artifacts()
        if not artifacts:
            await cl.Message(content="📦 No saved artifacts yet. Artifacts are auto-saved from canvas documents.").send()
            return True

        lines = ["### 📦 Saved Artifacts\n"]
        for i, a in enumerate(artifacts[:15], 1):
            ts = a["created_at"][:16].replace("T", " ") if a["created_at"] else "?"
            lines.append(f"**{i}.** 📄 {a['title']} ({a['type']}) — `{ts}`")
            lines.append(f"   Preview: *{a['preview'][:100]}...*")
            lines.append(f"   → `/artifact {a['id'][:8]}`")
        await cl.Message(content="\n".join(lines)).send()
        return True

    # ── /artifact <id> ───────────────────────────────────────────────────
    if cmd.startswith("/artifact "):
        partial_id = query[10:].strip()
        artifacts = _load_artifacts()
        match = None
        for a in artifacts:
            if a["id"].startswith(partial_id):
                match = _load_artifact(a["id"])
                break
        if match:
            elements = [cl.Text(name=match["title"], content=match["content"], display="side")]
            await cl.Message(
                content=f"📄 **{match['title']}** — opened in side pane",
                elements=elements
            ).send()
        else:
            await cl.Message(content=f"❌ No artifact found matching `{partial_id}`").send()
        return True

    # ── /research ─────────────────────────────────────────────────────────
    if cmd == "/research":
        sessions = _load_research_sessions()
        if not sessions:
            await cl.Message(content="🔬 No saved research yet. Research is auto-saved in Research mode.").send()
            return True

        lines = ["### 🔬 Saved Research\n"]
        for i, s in enumerate(sessions[:15], 1):
            ts = s["created_at"][:16].replace("T", " ") if s["created_at"] else "?"
            lines.append(f"**{i}.** 🔍 {s['query'][:60]} — {s['source_count']} sources — `{ts}`")
            lines.append(f"   Model: `{s['model']}`  → `/research {s['id'][:8]}`")
        await cl.Message(content="\n".join(lines)).send()
        return True

    # ── /research <id> ───────────────────────────────────────────────────
    if cmd.startswith("/research ") and len(query) > 10:
        partial_id = query[10:].strip()
        sessions = _load_research_sessions()
        match = None
        for s in sessions:
            if s["id"].startswith(partial_id):
                match = _load_research(s["id"])
                break
        if match:
            sources_md = ""
            for i, src in enumerate(match.get("sources", [])[:10], 1):
                url = src.get("url", "")
                source_name = src.get("source", "?")
                sources_md += f"  [{i}] {source_name} — {url}\n"

            elements = [cl.Text(
                name=f"Research: {match['query'][:40]}",
                content=match.get("brief", "No brief available"),
                display="side",
            )]
            await cl.Message(
                content=(
                    f"### 🔬 Research: {match['query']}\n\n"
                    f"**Model:** `{match.get('model', '?')}`\n"
                    f"**Date:** {match['created_at'][:16].replace('T', ' ')}\n\n"
                    f"**Sources:**\n{sources_md}\n"
                    f"*Full brief opened in side pane.*"
                ),
                elements=elements,
            ).send()
        else:
            await cl.Message(content=f"❌ No research found matching `{partial_id}`").send()
        return True

    # ── /settings ─────────────────────────────────────────────────────────
    if cmd == "/settings":
        brain = cl.user_session.get("brain", "?")
        mode = cl.user_session.get("mode", "?")
        temp = cl.user_session.get("temperature", 0.1)
        sys_prompt = cl.user_session.get("system_prompt", "")
        models = LLMFactory.list_models()
        model_name = models.get(brain, brain)
        saved = _load_settings()

        await cl.Message(content=(
            "### ⚙️ Current Settings\n\n"
            f"| Setting | Value |\n"
            f"|---------|-------|\n"
            f"| Model | `{model_name}` |\n"
            f"| Model ID | `{brain}` |\n"
            f"| Mode | {mode.title()} |\n"
            f"| Temperature | {temp} |\n"
            f"| System Prompt | {sys_prompt[:60] + '...' if sys_prompt else 'Default'} |\n"
            f"| Auto-save Research | {'Yes' if saved.get('auto_save_research', True) else 'No'} |\n"
            f"| Auto-save Artifacts | {'Yes' if saved.get('auto_save_artifacts', True) else 'No'} |\n\n"
            "*Use ⚙️ Settings icon to modify, or `/use <model_id>` to switch models.*"
        )).send()
        return True

    # ── /stats ────────────────────────────────────────────────────────────
    if cmd == "/stats":
        s = _stats()
        elapsed = round(time.time() - s["start"])
        brain = cl.user_session.get("brain", "?")
        models = LLMFactory.list_models()
        model_name = models.get(brain, brain)
        thread_count = len(_load_threads())
        artifact_count = len(_load_artifacts())
        research_count = len(_load_research_sessions())

        await cl.Message(content=(
            "### 📊 Session Statistics\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Turns | {s['turns']} |\n"
            f"| Sources Retrieved | {s['sources']} |\n"
            f"| Uptime | {elapsed}s |\n"
            f"| Active Model | {model_name} |\n"
            f"| Saved Conversations | {thread_count} |\n"
            f"| Saved Artifacts | {artifact_count} |\n"
            f"| Saved Research | {research_count} |\n"
        )).send()
        return True

    # ── /clear ────────────────────────────────────────────────────────────
    if cmd == "/clear":
        cl.user_session.set("thread_messages", [])
        cl.user_session.set("session_summary", None)
        cl.user_session.set("thread_id", str(uuid.uuid4()))
        cl.user_session.set("stats", {
            "turns": 0, "tokens": 0, "sources": 0, "start": time.time(),
        })
        await cl.Message(content="🗑️ Session cleared. Starting fresh!").send()
        return True

    # ── /help ─────────────────────────────────────────────────────────────
    if cmd == "/help":
        await cl.Message(content=(
            "### 📖 Commands\n\n"
            "| Command | Description |\n"
            "|---------|------------|\n"
            "| `/models` | List all available models |\n"
            "| `/use <id>` | Quick-switch to a model |\n"
            "| `/history` | Browse past conversations |\n"
            "| `/load <id>` | Resume a saved conversation |\n"
            "| `/save [title]` | Save current conversation |\n"
            "| `/artifacts` | Browse saved artifacts |\n"
            "| `/artifact <id>` | View a saved artifact |\n"
            "| `/research` | Browse saved research |\n"
            "| `/settings` | View current settings |\n"
            "| `/stats` | Session statistics |\n"
            "| `/clear` | Clear session & start fresh |\n"
            "| `/help` | Show this help |\n"
        )).send()
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════════════════════

@cl.on_message
async def on_message(message: cl.Message):
    query = message.content.strip()
    thread_id = cl.user_session.get("thread_id", "default")

    # ── Handle slash commands ─────────────────────────────────────────────
    if query.startswith("/"):
        handled = await _handle_command(query)
        if handled:
            return

    # ── Show thinking indicator ───────────────────────────────────────────
    brain = cl.user_session.get("brain", "groq/llama-3.3-70b-versatile")
    mode = cl.user_session.get("mode", "standard")
    temperature = cl.user_session.get("temperature", 0.1)
    system_prompt = cl.user_session.get("system_prompt", "")

    models = LLMFactory.list_models()
    model_name = models.get(brain, brain.split("/")[-1])

    thinking_msg = cl.Message(content=f"⏳ *Thinking with **{model_name}** ({mode} mode)…*")
    await thinking_msg.send()

    # ── Build initial state ───────────────────────────────────────────────
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "turn_count": _stats().get("turns", 0),
        "evidence": [],
        "artifacts": [],
        "node_timings": {},
        "completed_nodes": [],
        "errors": [],
        "session_summary": cl.user_session.get("session_summary"),
        "agent_mode": mode,
        "selected_model": brain,
    }

    # ── Run the graph ─────────────────────────────────────────────────────
    try:
        final_state = {}
        for event in graph.stream(initial_state):
            for node_id, node_state in event.items():
                final_state.update(node_state)

        # Persist session summary
        if final_state.get("session_summary"):
            cl.user_session.set("session_summary", final_state["session_summary"])

    except Exception as e:
        err = str(e)
        hint = ""
        if "401" in err or "AuthenticationError" in err:
            hint = "\n\n💡 Check your API key in Settings."
        elif "Connection" in err or "refused" in err.lower():
            hint = "\n\n📡 Connection failed. Is the model provider running?"
        elif "rate" in err.lower() or "429" in err:
            hint = "\n\n⏱️ Rate limited. Wait a moment and try again."
        elif "model" in err.lower() and ("not found" in err.lower() or "does not exist" in err.lower()):
            hint = "\n\n💡 Model not available. Try switching to a different model with `/models`."

        await thinking_msg.remove()
        await cl.Message(content=f"❌ **Error**: {err}{hint}").send()
        _save_message("error", err, thread_id)
        return

    # ── Remove thinking indicator ─────────────────────────────────────────
    await thinking_msg.remove()

    # ── Extract answer ────────────────────────────────────────────────────
    answer = final_state.get("answer", "")
    if not answer:
        msgs = final_state.get("messages", [])
        for m in reversed(msgs):
            if isinstance(m, AIMessage):
                answer = m.content
                break
        if not answer:
            answer = "No response generated."

    # ── Canvas detection & artifact saving ────────────────────────────────
    canvas_re = r"<canvas:\s*(.*?)>(.*?)</canvas>"
    matches = list(re.finditer(canvas_re, answer, re.DOTALL))

    clean_answer = answer
    elements: List[cl.Text] = []

    for match in matches:
        title = match.group(1).strip() or "Document"
        body = match.group(2).strip()
        clean_answer = clean_answer.replace(
            match.group(0),
            f"\n\n> 📄 **{title}** — *open in side pane*\n"
        )
        elements.append(cl.Text(name=title, content=body, display="side"))

        # Auto-save artifact
        saved_settings = _load_settings()
        if saved_settings.get("auto_save_artifacts", True):
            artifact_id = _save_artifact(title, body, "canvas")

    # ── Source citations at bottom ────────────────────────────────────────
    evidence = final_state.get("evidence", [])
    if evidence:
        web_sources = [e for e in evidence if e.get("type") == "web" and e.get("url")]
        if web_sources:
            clean_answer += "\n\n---\n**Sources:**\n"
            seen_urls = set()
            for e in web_sources[:8]:
                url = e.get("url", "")
                if url and url not in seen_urls:
                    source_name = e.get("source", "Web")
                    clean_answer += f"- [{source_name}]({url})\n"
                    seen_urls.add(url)

    # ── Send response ─────────────────────────────────────────────────────
    await cl.Message(content=clean_answer, elements=elements).send()

    # ── Update stats, save message, save thread ───────────────────────────
    evidence_count = len(evidence)
    _bump_stats(evidence_count)
    _save_message("user", query, thread_id)
    _save_message("assistant", answer[:2000], thread_id)

    # Track messages for thread saving
    thread_messages = cl.user_session.get("thread_messages", [])
    thread_messages.append({"role": "user", "content": query, "ts": datetime.now(timezone.utc).isoformat()})
    thread_messages.append({"role": "assistant", "content": answer[:2000], "ts": datetime.now(timezone.utc).isoformat()})
    cl.user_session.set("thread_messages", thread_messages)

    # ── Auto-save research if in research mode ────────────────────────────
    if mode == "research" and evidence:
        saved_settings = _load_settings()
        if saved_settings.get("auto_save_research", True):
            sources_data = [{"source": e.get("source"), "url": e.get("url"), "claim": e.get("claim", "")[:300]} for e in evidence]
            _save_research(query, answer[:2000], sources_data, brain)
