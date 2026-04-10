#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class ModelOption:
    value: str
    provider: str
    label: str
    note: str


CATALOG: Dict[str, List[ModelOption]] = {
    "RESEARCH_MODEL_GROQ": [
        ModelOption(
            "openai/gpt-oss-120b",
            "Groq",
            "GPT OSS 120B",
            "Best free Groq option for reasoning and tool use",
        ),
        ModelOption(
            "llama-3.3-70b-versatile",
            "Groq",
            "Llama 3.3 70B",
            "High quality, approx 1k req/day on free tier",
        ),
        ModelOption(
            "llama-3.1-8b-instant",
            "Groq",
            "Llama 3.1 8B Instant",
            "Fast workhorse, high daily quota",
        ),
        ModelOption(
            "llama-4-scout-17b",
            "Groq",
            "Llama 4 Scout 17B",
            "Best for larger prompt context",
        ),
    ],
    "TRANSLATION_MODEL_SARVAM": [
        ModelOption(
            "sarvam-translate",
            "Sarvam",
            "Sarvam Translate",
            "Primary translation model",
        ),
    ],
    "OLLAMA_FALLBACK_MODEL": [
        ModelOption(
            "deepseek-r1:8b",
            "Ollama",
            "DeepSeek R1 8B",
            "Good local reasoning fallback",
        ),
        ModelOption("qwen2.5:7b", "Ollama", "Qwen 2.5 7B", "Fast local general model"),
        ModelOption("llama3.1:8b", "Ollama", "Llama 3.1 8B", "Reliable local fallback"),
    ],
    "GROQ_MODEL_STRONG": [
        ModelOption(
            "openai/gpt-oss-120b",
            "Groq",
            "GPT OSS 120B",
            "Semantic router strong model",
        ),
        ModelOption(
            "llama-3.3-70b-versatile", "Groq", "Llama 3.3 70B", "Strong alternate"
        ),
    ],
    "GROQ_MODEL_FAST": [
        ModelOption(
            "llama-3.1-8b-instant",
            "Groq",
            "Llama 3.1 8B Instant",
            "Semantic router fast model",
        ),
        ModelOption(
            "llama-4-scout-17b",
            "Groq",
            "Llama 4 Scout 17B",
            "High throughput and context",
        ),
    ],
}


def parse_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def update_env(path: Path, updates: Dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for key, value in updates.items():
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def show_catalog(current: Dict[str, str]) -> None:
    print("=" * 100)
    print("MODEL CATALOG (BY ROLE)")
    print("=" * 100)
    for env_key, options in CATALOG.items():
        print(f"\n{env_key}")
        print("-" * 100)
        print(f"Current: {current.get(env_key, '<unset>')}")
        for index, option in enumerate(options, start=1):
            print(
                f"  {index}. {option.label:<30} | Provider: {option.provider:<10} | "
                f"Value: {option.value:<45} | {option.note}"
            )


def prompt_selection(current: Dict[str, str]) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    print("\nSelect models by number. Press Enter to keep current value.")
    for env_key, options in CATALOG.items():
        print(f"\n{env_key}")
        for index, option in enumerate(options, start=1):
            print(f"  {index}. {option.label} ({option.value})")

        choice = input(
            f"Choose 1-{len(options)} (current: {current.get(env_key, '<unset>')}): "
        ).strip()
        if not choice:
            continue
        if not choice.isdigit():
            print("  Invalid input, skipping.")
            continue

        idx = int(choice)
        if idx < 1 or idx > len(options):
            print("  Out of range, skipping.")
            continue

        updates[env_key] = options[idx - 1].value
    return updates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display model catalog and optionally update .env model defaults."
    )
    parser.add_argument(
        "--show-only",
        action="store_true",
        help="Only show model catalog, do not prompt for changes",
    )
    parser.add_argument("--env", default=str(ENV_PATH), help="Path to .env file")
    args = parser.parse_args()

    env_path = Path(args.env)
    if not env_path.exists():
        raise SystemExit(f"Missing env file: {env_path}")

    current = parse_env(env_path)
    show_catalog(current)

    if args.show_only:
        return

    updates = prompt_selection(current)
    if not updates:
        print("\nNo changes selected.")
        return

    update_env(env_path, updates)
    print("\nUpdated model settings:")
    for key, value in updates.items():
        print(f"  {key}={value}")


if __name__ == "__main__":
    main()
