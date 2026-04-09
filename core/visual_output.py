from __future__ import annotations

import json
import re
from typing import Any


VISUAL_TYPES = {
    "chart",
    "scoreboard",
    "table",
    "timeline",
    "diagram",
    "graph",
    "illustration",
}

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
  7. <visual type="diagram">VALID_JSON</visual> for system architecture, neural networks, pipelines, flowcharts, decision trees, data flow, state machines, concept maps, org charts, sequence diagrams, dependency graphs.
  8. <visual type="graph">VALID_JSON</visual> for scatter plots, bubble charts, network graphs, sankey diagrams, force-directed graphs, parallel coordinates.
  9. <visual type="illustration">VALID_JSON</visual> for beautiful intuition-building scenes, conceptual teaching visuals, or premium explainers where flat diagrams feel too mechanical.
  10. <node-graph>VALID_JSON</node-graph> for concept or entity maps.
  11. ```scorecard VALID_JSON``` for audits, evaluations, or scored reviews.
  12. ```mermaid``` ONLY as a last resort when no other format works.
- Never emit unsupported custom tags, raw HTML widgets, or partial blocks.
- JSON inside <visual>, <node-graph>, ```chart, and ```scorecard must be strict JSON:
  use double quotes, no comments, no trailing commas, no markdown inside the JSON.
- For <visual type="diagram"> use this structured spec:
  {
    "type": "diagram",
    "diagramType": "neural_network|pipeline|system_architecture|flowchart|decision_tree|data_flow|state_machine|concept_map|org_chart|sequence|dependency_graph",
    "title": "Short descriptive title",
    "subtitle": "Optional subtitle",
    "nodes": [
      {"id": "x1", "type": "input|process|output|concept|decision|data|function|system", "label": "Node label", "group": "optional-group", "description": "What this node does", "detail": "Extra detail shown on click", "icon": "optional-icon-key", "weight": 1}
    ],
    "edges": [
      {"source": "x1", "target": "x2", "label": "relationship", "type": "default|smoothstep|step|straight", "animated": true, "description": "What this edge means"}
    ],
    "style": {"theme": "modern-3d-education|minimal-clean|glassmorphism|neon-tech|warm-academic", "layout": "hierarchical|radial|force-directed|tree|flowchart", "edgeStyle": "gradient|solid|dashed|dotted", "nodeShape": "rounded|pill|card|circle", "animation": "subtle|moderate|dynamic|none"},
    "legend": [{"label": "Input", "color": "#6EE7B7"}]
  }
- For <visual type="graph"> use this structured spec:
  {
    "type": "graph",
    "graphType": "scatter|bubble|network|sankey|force|parallel",
    "title": "Short descriptive title",
    "subtitle": "Optional subtitle",
    "data": [{"x": 1, "y": 2, "size": 10, "category": "A"}],
    "xKey": "x",
    "yKey": "y",
    "sizeKey": "size",
    "colorKey": "category",
    "style": {"theme": "modern-3d-education"}
  }
- For <visual type="illustration"> use this structured spec:
  {
    "type": "illustration",
    "title": "Short descriptive title",
    "prompt": "Detailed visual prompt describing a beautiful and understandable scene with clear hierarchy and subject separation",
    "style": "cinematic 3d educational render|glassmorphism concept illustration|scientific teaching visual|premium product-grade explainer",
    "aspectRatio": "16:9|4:3|1:1|3:2",
    "caption": "Optional one-line explanation of what the image is showing"
  }
- For illustrations, prefer scenes that make the idea easier to grasp at a glance.
- Use depth, lighting, and composition to clarify relationships.
- Do not ask for embedded text labels inside the image.
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
                    return value[start : index + 1]
    return value


def _repair_json_text(raw: str) -> str:
    value = _extract_balanced_json_candidate(_strip_nested_fences(raw))
    value = (
        value.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
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
