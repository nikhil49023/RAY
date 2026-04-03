#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.skills import SkillToolkit


SECRET_FIELDS = [
    ("GROQ_API_KEY", "Groq API Key", "Used for Groq chat and fallback reasoning."),
    ("OPENROUTER_API_KEY", "OpenRouter API Key", "Used for OpenRouter-compatible chat calls."),
    ("LITELLM_MASTER_KEY", "LiteLLM Master Key", "Master key used by the local LiteLLM router service."),
    ("LITELLM_API_KEY", "LiteLLM Client Key", "Used by CrewAI/LangChain against your local LiteLLM router."),
    ("FIRECRAWL_API_KEY", "Firecrawl API Key", "Used for scraping and crawling pages."),
    ("SARVAM_API_KEY", "Sarvam API Key", "Used for translation requests."),
    ("HUGGINGFACE_API_TOKEN", "Hugging Face API Token", "Used for image generation requests."),
]


TEXT_FIELDS = [
    ("FIRECRAWL_BASE_URL", "Firecrawl Base URL", "Base URL for the Firecrawl API or self-hosted service."),
    ("OPENROUTER_BASE_URL", "OpenRouter Base URL", "OpenRouter-compatible endpoint."),
    ("OLLAMA_BASE_URL", "Ollama Base URL", "Local Ollama endpoint used by the Python agent."),
    ("LITELLM_BASE_URL", "LiteLLM Base URL", "OpenAI-compatible local LiteLLM endpoint."),
    ("LITELLM_MODEL", "LiteLLM Model Alias", "Model alias used by CrewAI/LangChain (for example premium-thinker)."),
    ("RAG_CHROMA_HOST", "RAG Chroma Host", "Host running the Chroma service for local retrieval."),
    ("RAG_CHROMA_PORT", "RAG Chroma Port", "Port for the Chroma service."),
    ("RAG_COLLECTION_NAME", "RAG Collection", "Collection name used for local document retrieval."),
    ("RAG_EMBEDDING_MODEL", "RAG Embedding Model", "Ollama embedding model name used for local search."),
    ("RAG_TOP_K", "RAG Top K", "Number of local chunks returned per retrieval query."),
    ("AGENTIC_SYSTEM_PROMPT", "Agentic System Prompt", "Global behavior instructions injected into autonomous runs."),
    ("BEHAVIOR_MEMORY_ENABLED", "Behavior Memory Enabled", "Enable/disable behavioral memory extraction and retrieval."),
    ("BEHAVIOR_MEMORY_COLLECTION", "Behavior Memory Collection", "Chroma collection name for behavioral reinforcement memory."),
    ("BEHAVIOR_MEMORY_TOP_K", "Behavior Memory Top K", "Number of behavioral rules injected per user query."),
    ("HARDWARE_VRAM_BUDGET_GB", "Hardware VRAM Budget (GB)", "UI/runtime guidance value for constrained local setup."),
    ("HARDWARE_QUANTIZATION_PROFILE", "Quantization Profile", "Recommended quantization strategy shown in the UI."),
]


DEFAULT_ARTIFACTS_DIR = "data/artifacts"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def upsert_env_value(lines: list[str], key: str, value: str) -> list[str]:
    updated_lines = lines[:]
    replacement = f"{key}={value}"
    for index, line in enumerate(updated_lines):
        if line.startswith(f"{key}="):
            updated_lines[index] = replacement
            break
    else:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append(replacement)
    return updated_lines


def save_env(path: Path, updates: dict[str, str]) -> None:
    if not path.exists() and ENV_EXAMPLE_PATH.exists():
        shutil.copyfile(ENV_EXAMPLE_PATH, path)

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    for key, value in updates.items():
        lines = upsert_env_value(lines, key, value)

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def render_field(field_key: str, label: str, help_text: str, current_value: str, secret: bool) -> str:
    if secret:
        return st.text_input(label, value=current_value, type="password", help=help_text)
    return st.text_input(label, value=current_value, help=help_text)


def resolve_artifacts_dir(current_env: dict[str, str]) -> Path:
    raw_dir = current_env.get("ARTIFACTS_DIR", DEFAULT_ARTIFACTS_DIR).strip() or DEFAULT_ARTIFACTS_DIR
    path = Path(raw_dir)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"


def render_settings_tab(current: dict[str, str]) -> None:
    if not ENV_PATH.exists():
        st.warning(".env does not exist yet. Saving will create it from .env.example when available.")

    with st.form("settings-form"):
        st.subheader("API Keys")
        secret_updates: dict[str, str] = {}
        secret_columns = st.columns(2)
        for index, (key, label, help_text) in enumerate(SECRET_FIELDS):
            column = secret_columns[index % len(secret_columns)]
            with column:
                secret_updates[key] = render_field(key, label, help_text, current.get(key, ""), secret=True)

        st.subheader("Service Endpoints")
        text_updates: dict[str, str] = {}
        text_columns = st.columns(3)
        for index, (key, label, help_text) in enumerate(TEXT_FIELDS):
            column = text_columns[index % len(text_columns)]
            with column:
                text_updates[key] = render_field(key, label, help_text, current.get(key, ""), secret=False)

        submitted = st.form_submit_button("Save to .env")

    if submitted:
        save_env(ENV_PATH, {**secret_updates, **text_updates})
        st.success("Saved .env successfully.")
        st.rerun()

    st.divider()
    st.subheader("Current status")
    status_columns = st.columns(3)
    with status_columns[0]:
        st.metric("Groq key", "set" if current.get("GROQ_API_KEY") else "missing")
        st.metric("OpenRouter key", "set" if current.get("OPENROUTER_API_KEY") else "missing")
    with status_columns[1]:
        st.metric("LiteLLM key", "set" if current.get("LITELLM_API_KEY") else "missing")
        st.metric("Firecrawl key", "set" if current.get("FIRECRAWL_API_KEY") else "missing")
        st.metric("Sarvam key", "set" if current.get("SARVAM_API_KEY") else "missing")
    with status_columns[2]:
        st.metric("Hugging Face token", "set" if current.get("HUGGINGFACE_API_TOKEN") else "missing")
        st.metric("Chainlit port", current.get("CHAINLIT_PORT", "8001"))
        st.metric("Behavior memory", "on" if current.get("BEHAVIOR_MEMORY_ENABLED", "true").lower() in {"1", "true", "yes", "on"} else "off")


def render_canvas_tab(current: dict[str, str]) -> None:
    st.subheader("Document Drafting Canvas")
    st.caption("Write markdown and export it as a DOCX or PDF artifact.")

    artifacts_dir = resolve_artifacts_dir(current)
    toolkit = SkillToolkit(output_dir=str(artifacts_dir))

    default_markdown = (
        "# Executive Summary\n"
        "- Add your key points here\n"
        "\n"
        "## Details\n"
        "Write the long-form draft in markdown."
    )

    with st.form("draft-canvas-form"):
        title = st.text_input("Document title", value="Project Brief")
        output_format = st.selectbox("Output format", ["docx", "pdf"], index=0)
        markdown = st.text_area("Markdown canvas", value=default_markdown, height=360)
        draft_submitted = st.form_submit_button("Generate Artifact")

    if draft_submitted:
        if not title.strip():
            st.error("Document title is required.")
            return
        result = toolkit.generate_document(title=title, markdown=markdown, output_format=output_format)
        result_path = Path(result["path"])
        st.success(f"Created {output_format.upper()} artifact: {result_path.name}")
        if result_path.exists():
            st.download_button(
                label=f"Download {result_path.name}",
                data=result_path.read_bytes(),
                file_name=result_path.name,
                mime="application/octet-stream",
                key=f"download-{result_path.name}",
            )
        st.code(markdown[:3000])


def render_artifacts_tab(current: dict[str, str]) -> None:
    st.subheader("Artifacts")
    artifacts_dir = resolve_artifacts_dir(current)

    if st.button("Refresh Artifacts"):
        st.rerun()

    files = [p for p in artifacts_dir.glob("**/*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    st.caption(f"Directory: {artifacts_dir}")
    st.metric("Total artifacts", str(len(files)))

    if not files:
        st.info("No artifacts found yet. Use the Document Drafting Canvas tab to generate one.")
        return

    for file_path in files:
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        rel_path = file_path.relative_to(ROOT_DIR) if file_path.is_relative_to(ROOT_DIR) else file_path
        with st.expander(f"{file_path.name} ({human_size(stat.st_size)})"):
            st.write(f"Path: {rel_path}")
            st.write(f"Modified: {modified}")

            suffix = file_path.suffix.lower()
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                st.image(str(file_path), use_container_width=True)
            elif suffix in {".txt", ".md", ".json", ".html", ".csv", ".log"}:
                text_preview = file_path.read_text(encoding="utf-8", errors="replace")[:5000]
                st.code(text_preview)

            st.download_button(
                label=f"Download {file_path.name}",
                data=file_path.read_bytes(),
                file_name=file_path.name,
                mime="application/octet-stream",
                key=f"download-{file_path}",
            )


def main() -> None:
    st.set_page_config(page_title="RAY Settings", page_icon="⚙️", layout="wide")
    st.title("RAY Control Center")
    st.caption("Configure keys, draft documents in a canvas, and browse generated artifacts.")

    current = load_env(ENV_PATH)

    settings_tab, canvas_tab, artifacts_tab = st.tabs(["Settings", "Drafting Canvas", "Artifacts"])
    with settings_tab:
        render_settings_tab(current)
    with canvas_tab:
        render_canvas_tab(current)
    with artifacts_tab:
        render_artifacts_tab(current)


if __name__ == "__main__":
    main()
