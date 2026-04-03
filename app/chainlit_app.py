from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

import chainlit as cl
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.agentic_orchestrator import AgenticOrchestrator
from agents.behavioral_memory import BehavioralMemory
from agents.config import settings

MEMORY_DIR = ROOT_DIR / "data" / "memory"
MEMORY_FILE = MEMORY_DIR / "chainlit_history.jsonl"

DEFAULT_MODEL_CHOICES = [
    "premium-thinker",
    "premium-fast",
    settings.groq_model_strong,
    settings.groq_model_quality,
    settings.groq_model_fast,
    settings.groq_model_long_context,
    settings.openrouter_model_auto_free,
    settings.openrouter_model_fast_free,
    settings.openrouter_model_coding_free,
    settings.openrouter_model_multimodal_free,
]


def _append_memory(role: str, content: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "content": content[:4000],
    }
    with MEMORY_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True) + "\n")


def _recent_memory(limit: int = 8) -> List[Dict[str, str]]:
    if not MEMORY_FILE.exists():
        return []
    lines = MEMORY_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    rows: List[Dict[str, str]] = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _is_firecrawl_ready(base_url: str | None = None, api_key: str | None = None) -> bool:
    base_url = _normalize_base_url(base_url or settings.firecrawl_base_url)
    api_key = (api_key if api_key is not None else settings.firecrawl_api_key).strip()
    if not base_url:
        return False
    if base_url == "https://api.firecrawl.dev":
        return bool(api_key)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        for endpoint in ("/health", "/v2/health", "/v1/health", ""):
            response = requests.get(base_url + endpoint, headers=headers, timeout=2)
            if response.status_code < 500:
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _is_litellm_ready(base_url: str | None = None, api_key: str | None = None) -> bool:
    base_url = _normalize_base_url(base_url or settings.litellm_base_url)
    api_key = (api_key if api_key is not None else settings.litellm_api_key).strip()
    if not base_url:
        return False

    models_url = base_url + "/models" if base_url.endswith("/v1") else base_url + "/v1/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(models_url, headers=headers, timeout=2)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _is_ollama_ready() -> bool:
    base = _normalize_base_url(settings.ollama_base_url)
    if not base:
        return False

    probes = [base]
    if "://ollama" in base:
        probes.append(base.replace("://ollama", "://localhost"))

    for probe in probes:
        try:
            response = requests.get(probe + "/api/tags", timeout=2)
            if response.status_code == 200:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _chroma_collection_names(client: Any) -> List[str]:
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


def _is_rag_ready() -> bool:
    try:
        if importlib.util.find_spec("chromadb") is None:
            return False
        chromadb = importlib.import_module("chromadb")
        collection_name = settings.rag_collection_name

        try:
            remote = chromadb.HttpClient(host=settings.rag_chroma_host, port=settings.rag_chroma_port)
            remote.heartbeat()
            names = _chroma_collection_names(remote)
            return collection_name in names or bool(remote.get_collection(name=collection_name))
        except Exception:  # noqa: BLE001
            pass

        local_path = Path(settings.rag_chroma_local_path)
        if not local_path.is_absolute():
            local_path = ROOT_DIR / local_path
        local = chromadb.PersistentClient(path=str(local_path))
        local.heartbeat()
        names = _chroma_collection_names(local)
        return collection_name in names or bool(local.get_collection(name=collection_name))
    except Exception:  # noqa: BLE001
        return False


def _scoreboard(
    mode: str,
    artifact_path: str | None,
    readiness: Dict[str, bool],
    dashboard_style: str,
) -> go.Figure:
    labels = ["Crew", "Artifact", "RAG", "Firecrawl", "LiteLLM", "Ollama", "Memory Injected"]
    values = [
        1 if mode == "crewai" else 0,
        1 if artifact_path else 0,
        1 if readiness.get("rag", False) else 0,
        1 if readiness.get("firecrawl", False) else 0,
        1 if readiness.get("litellm", False) else 0,
        1 if readiness.get("ollama", False) else 0,
        1 if readiness.get("behavioral_injected", False) else 0,
    ]
    style = dashboard_style.strip().lower()
    if style == "executive":
        ready_color, blocked_color, bg_color = "#2563eb", "#be123c", "#f8fafc"
    elif style == "diagnostic":
        ready_color, blocked_color, bg_color = "#16a34a", "#b91c1c", "#f3f4f6"
    else:
        ready_color, blocked_color, bg_color = "#0f766e", "#b91c1c", "#ffffff"

    colors = [ready_color if val else blocked_color for val in values]

    figure = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.24,
        specs=[[{"type": "indicator"}], [{"type": "bar"}]],
    )
    ready_count = sum(values)
    figure.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=float(ready_count),
            number={"suffix": f"/{len(values)}"},
            title={"text": "Runtime Health"},
            gauge={
                "axis": {"range": [0, len(values)]},
                "bar": {"color": ready_color},
                "bgcolor": "#e5e7eb",
            },
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=["ready" if val else "blocked" for val in values],
            textposition="outside",
        ),
        row=2,
        col=1,
    )
    figure.update_layout(
        title=(
            f"God Mode Runtime | VRAM Budget: {settings.hardware_vram_budget_gb}GB | "
            f"Quantization: {settings.hardware_quantization_profile}"
        ),
        yaxis2=dict(range=[0, 1.2], tickvals=[0, 1], ticktext=["blocked", "ready"]),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        height=520,
        margin=dict(l=20, r=20, t=50, b=30),
    )
    return figure


def _compose_behavior_injection(base_prompt: str, behaviors: List[str]) -> str:
    clean_behaviors = [item.strip() for item in behaviors if item.strip()]
    if not clean_behaviors:
        return base_prompt
    behavior_block = "Persistent Behavioral Preferences:\n" + "\n".join(f"- {item}" for item in clean_behaviors)
    return base_prompt.strip() + "\n\n" + behavior_block


def _extract_urls(prompt: str) -> List[str]:
    pattern = re.compile(r"https?://[^\s]+", flags=re.IGNORECASE)
    return pattern.findall(prompt)


def _render_summary(result: Dict[str, Any]) -> str:
    status = str(result.get("status", "unknown"))
    mode = str(result.get("mode", "unknown"))
    reason = str(result.get("reason", "")).strip()
    answer = str(result.get("answer", "")).strip()
    artifact = str(result.get("visualization_artifact", "")).strip()

    lines = [f"Status: {status}", f"Mode: {mode}"]
    if reason:
        lines.append(f"Reason: {reason}")
    if answer:
        lines.extend(["", answer])
    if artifact:
        lines.extend(["", f"Artifact: {artifact}"])
    return "\n".join(lines)


def _model_choices() -> List[str]:
    ordered: List[str] = []
    for item in DEFAULT_MODEL_CHOICES:
        model = (item or "").strip()
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def _normalize_model(selected_choice: str, custom_model: str) -> str:
    custom = (custom_model or "").strip()
    if custom:
        return custom
    return (selected_choice or settings.litellm_model).strip()


def _safe_theme(value: str) -> str:
    theme = (value or "").strip().lower()
    if theme in {"light", "dark"}:
        return theme
    return "system"


def _theme_notice(theme: str) -> str:
    if theme == "system":
        return "Theme preference: system"
    return f"Theme preference: {theme}"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@cl.on_chat_start
async def on_chat_start() -> None:
    orchestrator = AgenticOrchestrator()
    cl.user_session.set("orchestrator", orchestrator)
    behavior_memory = BehavioralMemory()
    cl.user_session.set("behavior_memory", behavior_memory)

    choices = _model_choices()
    default_model = settings.litellm_model if settings.litellm_model in choices else choices[0]

    chat_settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="primary_model",
                label="Primary Model",
                values=choices,
                initial_index=choices.index(default_model),
            ),
            cl.input_widget.TextInput(
                id="custom_model",
                label="Custom Model (optional)",
                initial="",
                placeholder="e.g. groq/llama-3.3-70b-versatile",
            ),
            cl.input_widget.TextInput(
                id="system_prompt",
                label="System Prompt",
                initial=settings.agentic_system_prompt,
                placeholder="High-level behavior instructions for the autonomous agent",
            ),
            cl.input_widget.Switch(
                id="behavior_memory_enabled",
                label="Behavior Memory",
                initial=settings.behavior_memory_enabled,
            ),
            cl.input_widget.Slider(
                id="behavior_memory_top_k",
                label="Behavior Memory Top K",
                initial=float(settings.behavior_memory_top_k),
                min=1,
                max=8,
                step=1,
            ),
            cl.input_widget.Select(
                id="dashboard_style",
                label="Dashboard Style",
                values=["minimalist", "diagnostic", "executive"],
                initial_index=0,
            ),
            cl.input_widget.Switch(
                id="auto_capture_feedback",
                label="Auto Capture Feedback",
                initial=True,
            ),
            cl.input_widget.TextInput(
                id="litellm_base_url",
                label="LiteLLM Base URL",
                initial=settings.litellm_base_url,
                placeholder="http://localhost:4000/v1",
            ),
            cl.input_widget.TextInput(
                id="litellm_api_key",
                label="LiteLLM API Key",
                initial=settings.litellm_api_key,
                placeholder="sk-litellm-master-key",
            ),
            cl.input_widget.TextInput(
                id="firecrawl_base_url",
                label="Firecrawl Base URL",
                initial=settings.firecrawl_base_url,
                placeholder="http://localhost:3002",
            ),
            cl.input_widget.TextInput(
                id="firecrawl_api_key",
                label="Firecrawl API Key (optional for self-host)",
                initial=settings.firecrawl_api_key,
                placeholder="leave empty for self-host if not required",
            ),
            cl.input_widget.Switch(
                id="enable_crewai",
                label="Enable CrewAI",
                initial=settings.agentic_enable_crewai,
            ),
            cl.input_widget.Select(
                id="theme",
                label="Theme",
                values=["system", "light", "dark"],
                initial_index=0,
            ),
        ]
    ).send()
    cl.user_session.set("chat_settings", chat_settings)

    theme = _safe_theme(str(chat_settings.get("theme", "system")))
    memory_status = behavior_memory.status()

    memory_rows = _recent_memory(limit=6)
    memory_hint = ""
    if memory_rows:
        memory_hint = "\n\nRecent memory loaded from local JSON store."

    await cl.Message(
        content=(
            "## RAY Control Surface\n"
            "Autonomous orchestration is active with inline dashboards and behavioral memory.\n\n"
            f"- Hardware Profile: `{settings.hardware_vram_budget_gb}GB` VRAM budget, `{settings.hardware_quantization_profile}`\n"
            f"- Behavioral Memory: `{'ready' if memory_status.ready else 'fallback'}` via `{memory_status.backend}`\n"
            f"- Theme: `{theme}`\n\n"
            "Open chat settings in the sidebar to tune model routing, memory injection depth, and dashboard style."
            + memory_hint
        )
    ).send()


@cl.on_settings_update
async def on_settings_update(updated: Dict[str, Any]) -> None:
    cl.user_session.set("chat_settings", updated)
    theme = _safe_theme(str(updated.get("theme", "system")))
    behavior_memory_enabled = _as_bool(updated.get("behavior_memory_enabled", settings.behavior_memory_enabled))
    memory_top_k = int(float(updated.get("behavior_memory_top_k", settings.behavior_memory_top_k)))
    style = str(updated.get("dashboard_style", "minimalist")).strip().lower() or "minimalist"
    await cl.Message(
        content=(
            f"Settings updated. {_theme_notice(theme)} | "
            f"Behavior memory: {'on' if behavior_memory_enabled else 'off'} (top_k={memory_top_k}) | "
            f"Dashboard style: {style}"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    orchestrator = cl.user_session.get("orchestrator")
    if orchestrator is None:
        orchestrator = AgenticOrchestrator()
        cl.user_session.set("orchestrator", orchestrator)
    behavior_memory = cl.user_session.get("behavior_memory")
    if behavior_memory is None:
        behavior_memory = BehavioralMemory()
        cl.user_session.set("behavior_memory", behavior_memory)

    prompt = message.content.strip()
    if not prompt:
        await cl.Message(content="Please provide an objective.").send()
        return

    _append_memory("user", prompt)

    status_msg = cl.Message(content="Running God Mode orchestration...")
    await status_msg.send()

    runtime_settings = cl.user_session.get("chat_settings") or {}
    selected_model = _normalize_model(
        str(runtime_settings.get("primary_model", settings.litellm_model)),
        str(runtime_settings.get("custom_model", "")),
    )
    litellm_base_url = str(runtime_settings.get("litellm_base_url", settings.litellm_base_url)).strip()
    litellm_api_key = str(runtime_settings.get("litellm_api_key", settings.litellm_api_key)).strip()
    enable_crewai = _as_bool(runtime_settings.get("enable_crewai", settings.agentic_enable_crewai))
    system_prompt = str(runtime_settings.get("system_prompt", settings.agentic_system_prompt)).strip() or settings.agentic_system_prompt
    behavior_memory_enabled = _as_bool(runtime_settings.get("behavior_memory_enabled", settings.behavior_memory_enabled))
    behavior_memory_top_k = int(float(runtime_settings.get("behavior_memory_top_k", settings.behavior_memory_top_k)))
    dashboard_style = str(runtime_settings.get("dashboard_style", "minimalist")).strip().lower() or "minimalist"
    auto_capture_feedback = _as_bool(runtime_settings.get("auto_capture_feedback", True))

    firecrawl_base_url = str(runtime_settings.get("firecrawl_base_url", settings.firecrawl_base_url)).strip()
    firecrawl_api_key = str(runtime_settings.get("firecrawl_api_key", settings.firecrawl_api_key)).strip()

    applied_behaviors: List[str] = []
    if behavior_memory_enabled:
        try:
            applied_behaviors = behavior_memory.retrieve(prompt, top_k=behavior_memory_top_k)
        except Exception:  # noqa: BLE001
            applied_behaviors = []

    injected_system_prompt = _compose_behavior_injection(system_prompt, applied_behaviors)

    result = await cl.make_async(orchestrator.run_goal)(
        prompt,
        model_override=selected_model,
        litellm_base_url_override=litellm_base_url,
        litellm_api_key_override=litellm_api_key,
        firecrawl_base_url_override=firecrawl_base_url,
        firecrawl_api_key_override=firecrawl_api_key,
        enable_crewai_override=enable_crewai,
        system_prompt_override=injected_system_prompt,
    )

    captured_rules: List[str] = []
    if behavior_memory_enabled and auto_capture_feedback:
        try:
            captured_rules = behavior_memory.capture_feedback(prompt)
        except Exception:  # noqa: BLE001
            captured_rules = []

    readiness = {
        "rag": _is_rag_ready(),
        "firecrawl": _is_firecrawl_ready(base_url=firecrawl_base_url, api_key=firecrawl_api_key),
        "litellm": _is_litellm_ready(base_url=litellm_base_url, api_key=litellm_api_key),
        "ollama": _is_ollama_ready(),
        "behavioral_injected": bool(applied_behaviors),
    }

    artifact_path = str(result.get("visualization_artifact", "")).strip() or None
    elements: List[Any] = [
        cl.Plotly(
            name="runtime_scoreboard",
            figure=_scoreboard(str(result.get("mode", "")), artifact_path, readiness=readiness, dashboard_style=dashboard_style),
            display="inline",
        )
    ]

    if artifact_path:
        artifact_file = Path(artifact_path)
        if not artifact_file.is_absolute():
            artifact_file = ROOT_DIR / artifact_file
        if artifact_file.exists():
            elements.append(
                cl.File(
                    name=artifact_file.name,
                    path=str(artifact_file),
                    display="inline",
                )
            )
            if artifact_file.suffix.lower() in {".html", ".txt", ".md", ".json"}:
                preview = artifact_file.read_text(encoding="utf-8", errors="replace")[:6000]
                elements.append(cl.Text(name="artifact_preview", content=preview, display="side"))

    if applied_behaviors:
        elements.append(
            cl.Text(
                name="behavioral_memory_applied",
                content="Behavioral memory injected into system prompt:\n" + "\n".join(f"- {item}" for item in applied_behaviors),
                display="side",
            )
        )

    if captured_rules:
        elements.append(
            cl.Text(
                name="behavioral_memory_captured",
                content="New reinforcement rules captured this turn:\n" + "\n".join(f"- {item}" for item in captured_rules),
                display="side",
            )
        )

    urls = _extract_urls(prompt)
    if urls:
        elements.append(
            cl.Text(
                name="detected_urls",
                content="Detected URLs for potential Firecrawl use:\n" + "\n".join(urls),
                display="side",
            )
        )

    runtime_lines = [
        f"Model: {selected_model}",
        f"CrewAI: {'enabled' if enable_crewai else 'disabled'}",
        f"Behavior memory: {'enabled' if behavior_memory_enabled else 'disabled'}",
        f"Behavior rules injected: {len(applied_behaviors)}",
        f"RAG ready: {'yes' if readiness['rag'] else 'no'}",
        f"Firecrawl ready: {'yes' if readiness['firecrawl'] else 'no'}",
        f"LiteLLM ready: {'yes' if readiness['litellm'] else 'no'}",
        f"Ollama ready: {'yes' if readiness['ollama'] else 'no'}",
        f"VRAM profile: {settings.hardware_vram_budget_gb}GB",
        f"Quantization profile: {settings.hardware_quantization_profile}",
    ]
    elements.append(cl.Text(name="runtime_profile", content="\n".join(runtime_lines), display="side"))

    summary = _render_summary(result)
    summary = summary + f"\nModel: {selected_model}"
    if applied_behaviors:
        summary = summary + f"\nBehavior Memory Applied: {len(applied_behaviors)} rule(s)"
    if captured_rules:
        summary = summary + f"\nBehavior Rules Captured: {len(captured_rules)}"
    _append_memory("assistant", summary)

    await cl.Message(content=summary, elements=elements).send()
