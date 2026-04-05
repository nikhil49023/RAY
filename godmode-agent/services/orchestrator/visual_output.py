from __future__ import annotations

import json
import re
from typing import Any


VISUAL_TYPES = {"chart", "scoreboard", "table", "timeline"}

VISUAL_BLOCK_RE = re.compile(
    r'<visual\s+type="(?P<type>[^"]+)">(?P<body>[\s\S]*?)</visual>',
    re.IGNORECASE,
)
NODE_GRAPH_RE = re.compile(
    r"<node-graph>(?P<body>[\s\S]*?)</node-graph>",
    re.IGNORECASE,
)
CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>chart|scorecard|mermaid)\s*(?P<body>[\s\S]*?)```",
    re.IGNORECASE,
)


def build_visual_output_guidance(*, visuals_enabled: bool) -> str:
    if not visuals_enabled:
        return """\
Visual output contract:
- Return plain markdown only.
- Do not emit <document>, <canvas>, <visual>, <node-graph>, ```chart, ```scorecard, or ```mermaid blocks unless visual mode is enabled."""

    return """\
Visual output contract:
- Prefer plain markdown unless a visual materially improves understanding.
- Use only these structured formats:
  1. <document: Title>…</document> for structured research briefs.
  2. <canvas: Title>…</canvas> for long-form drafts or report-style output.
  3. <visual type="chart">VALID_JSON</visual> for quantitative comparisons or trends.
  4. <visual type="scoreboard">VALID_JSON</visual> for rankings or leaderboards.
  5. <visual type="table">VALID_JSON</visual> for feature comparisons.
  6. <visual type="timeline">VALID_JSON</visual> for dated events or milestones.
  7. <node-graph>VALID_JSON</node-graph> for concept or entity maps.
  8. ```scorecard VALID_JSON``` for audits, evaluations, or scored reviews.
  9. ```mermaid``` for diagrams only when a diagram is clearer than text.
- Never emit unsupported custom tags, raw HTML widgets, or partial blocks.
- JSON inside <visual>, <node-graph>, ```chart, and ```scorecard must be strict JSON:
  use double quotes, no comments, no trailing commas, no markdown inside the JSON.
- For <visual type="chart"> use:
  {
    "type": "chart",
    "chartType": "bar|line|area|pie",
    "title": "Short title",
    "xAxis": {"label": "Category", "values": ["A", "B"]},
    "series": [{"name": "Series 1", "values": [1, 2]}]
  }
- For <visual type="scoreboard"> use:
  {
    "type": "scoreboard",
    "title": "Short title",
    "rows": [{"rank": 1, "label": "Item", "score": 98, "change": "+2"}]
  }
- For <visual type="table"> use:
  {
    "type": "table",
    "title": "Short title",
    "columns": ["Feature", "Option A", "Option B"],
    "rows": [["Price", "$10", "$20"]]
  }
- For <visual type="timeline"> use:
  {
    "type": "timeline",
    "title": "Short title",
    "events": [{"date": "2026-04", "label": "Event", "category": "research"}]
  }
- For <node-graph> use:
  {
    "title": "Short title",
    "nodes": [{"id": "n1", "label": "Topic", "group": "concept", "weight": 2}],
    "edges": [{"source": "n1", "target": "n2", "label": "relates to"}]
  }
- For mermaid, emit standard Mermaid syntax only. Never write malformed edges like -->|Label|> B.
- If you are not fully confident the structure will be valid, fall back to plain markdown instead of a broken visual."""


def _strip_nested_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", value, count=1).strip()
        value = re.sub(r"\s*```$", "", value, count=1).strip()
    if value.lower().startswith("json"):
        value = value[4:].lstrip()
    return value.strip()


def _extract_balanced_json_candidate(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value
    starts = [("{", "}"), ("[", "]")]
    for opener, closer in starts:
        start = value.find(opener)
        if start < 0:
            continue
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(value)):
            char = value[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return value[start:index + 1]
    return value


def _repair_json_text(raw: str) -> str:
    value = _extract_balanced_json_candidate(_strip_nested_fences(raw))
    value = value.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    value = re.sub(r",(\s*[}\]])", r"\1", value)
    return value.strip()


def _parse_repaired_json(raw: str) -> Any | None:
    candidate = _repair_json_text(raw)
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except Exception:
        return None


def sanitize_mermaid_source(input_text: str) -> str:
    value = (input_text or "").replace("\r\n", "\n").strip()
    value = re.sub(r"\|([^|\n]+)\|>\s+", r"|\1| ", value)
    value = re.sub(r">>\s*([A-Za-z0-9_[(])", r"> \1", value)
    return value.strip()


def normalize_visual_response(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value

    def replace_visual(match: re.Match[str]) -> str:
        visual_type = str(match.group("type") or "").strip().lower()
        body = match.group("body") or ""
        if visual_type not in VISUAL_TYPES:
            return match.group(0)
        parsed = _parse_repaired_json(body)
        if parsed is None:
            return match.group(0)
        return f'<visual type="{visual_type}">\n{json.dumps(parsed, ensure_ascii=False, indent=2)}\n</visual>'

    def replace_node_graph(match: re.Match[str]) -> str:
        body = match.group("body") or ""
        parsed = _parse_repaired_json(body)
        if parsed is None:
            return match.group(0)
        return f"<node-graph>\n{json.dumps(parsed, ensure_ascii=False, indent=2)}\n</node-graph>"

    def replace_code(match: re.Match[str]) -> str:
        lang = str(match.group("lang") or "").strip().lower()
        body = match.group("body") or ""
        if lang == "mermaid":
            return f"```mermaid\n{sanitize_mermaid_source(body)}\n```"
        parsed = _parse_repaired_json(body)
        if parsed is None:
            return match.group(0)
        return f"```{lang}\n{json.dumps(parsed, ensure_ascii=False, indent=2)}\n```"

    value = VISUAL_BLOCK_RE.sub(replace_visual, value)
    value = NODE_GRAPH_RE.sub(replace_node_graph, value)
    value = CODE_BLOCK_RE.sub(replace_code, value)
    return value
