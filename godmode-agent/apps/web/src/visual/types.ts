export interface VisualNode {
  id: string
  label: string
  type: "input" | "process" | "output" | "concept" | "decision" | "data" | "function" | "system"
  group?: string
  description?: string
  detail?: string
  icon?: string
  weight?: number
  color?: string
  metadata?: Record<string, unknown>
}

export interface VisualEdge {
  source: string
  target: string
  label?: string
  type?: "default" | "smoothstep" | "step" | "straight"
  animated?: boolean
  style?: string
  description?: string
}

export interface VisualStyle {
  theme: "modern-3d-education" | "minimal-clean" | "glassmorphism" | "neon-tech" | "warm-academic"
  layout: "hierarchical" | "radial" | "force-directed" | "tree" | "flowchart"
  edgeStyle: "gradient" | "solid" | "dashed" | "dotted"
  nodeShape: "rounded" | "pill" | "card" | "circle"
  animation: "subtle" | "moderate" | "dynamic" | "none"
}

export interface DiagramSpec {
  type: "diagram"
  diagramType:
    | "neural_network"
    | "pipeline"
    | "system_architecture"
    | "flowchart"
    | "decision_tree"
    | "data_flow"
    | "state_machine"
    | "concept_map"
    | "org_chart"
    | "sequence"
    | "dependency_graph"
  title: string
  subtitle?: string
  nodes: VisualNode[]
  edges: VisualEdge[]
  style: Partial<VisualStyle>
  legend?: { label: string; color: string }[]
  source?: string
}

export interface GraphSpec {
  type: "graph"
  graphType: "scatter" | "bubble" | "network" | "sankey" | "force" | "parallel"
  title: string
  subtitle?: string
  data: Record<string, unknown>[]
  xKey?: string
  yKey?: string
  sizeKey?: string
  colorKey?: string
  style: Partial<VisualStyle>
  source?: string
}

export interface IllustrationSpec {
  type: "illustration"
  title: string
  prompt: string
  style: string
  aspectRatio?: string
  caption?: string
}

export type VisualSpec = DiagramSpec | GraphSpec | IllustrationSpec

export function isDiagramSpec(spec: VisualSpec): spec is DiagramSpec {
  return spec.type === "diagram"
}

export function isGraphSpec(spec: VisualSpec): spec is GraphSpec {
  return spec.type === "graph"
}

export function isIllustrationSpec(spec: VisualSpec): spec is IllustrationSpec {
  return spec.type === "illustration"
}

export const DEFAULT_STYLE: VisualStyle = {
  theme: "modern-3d-education",
  layout: "hierarchical",
  edgeStyle: "gradient",
  nodeShape: "rounded",
  animation: "subtle",
}

export const GROUP_COLORS: Record<string, string> = {
  input: "#2F6F72",
  process: "#4F7A9A",
  output: "#C58A57",
  concept: "#7C6FA8",
  decision: "#B95C6B",
  data: "#7A9E7E",
  function: "#A87B6B",
  system: "#5B7B8A",
}

export const THEME_PRESETS: Record<string, { bg: string; nodeBg: string; nodeBorder: string; text: string; textSecondary: string; edgeStroke: string; accent: string; shadow: string }> = {
  "modern-3d-education": {
    bg: "#0D0D12",
    nodeBg: "rgba(22, 22, 31, 0.92)",
    nodeBorder: "rgba(255, 255, 255, 0.06)",
    text: "#F1F5F9",
    textSecondary: "#8B95A5",
    edgeStroke: "rgba(139, 149, 165, 0.25)",
    accent: "#6EE7B7",
    shadow: "0 4px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.03)",
  },
  "minimal-clean": {
    bg: "#F8FAFC",
    nodeBg: "#FFFFFF",
    nodeBorder: "rgba(0, 0, 0, 0.08)",
    text: "#1E293B",
    textSecondary: "#64748B",
    edgeStroke: "rgba(0, 0, 0, 0.12)",
    accent: "#3B82F6",
    shadow: "0 2px 12px rgba(0, 0, 0, 0.06)",
  },
  "glassmorphism": {
    bg: "rgba(13, 13, 18, 0.7)",
    nodeBg: "rgba(22, 22, 31, 0.65)",
    nodeBorder: "rgba(255, 255, 255, 0.08)",
    text: "#F1F5F9",
    textSecondary: "#8B95A5",
    edgeStroke: "rgba(255, 255, 255, 0.12)",
    accent: "#6EE7B7",
    shadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
  },
  "neon-tech": {
    bg: "#08060E",
    nodeBg: "rgba(18, 14, 28, 0.9)",
    nodeBorder: "rgba(110, 231, 183, 0.15)",
    text: "#E2E8F0",
    textSecondary: "#64748B",
    edgeStroke: "rgba(110, 231, 183, 0.3)",
    accent: "#6EE7B7",
    shadow: "0 0 24px rgba(110, 231, 183, 0.08), 0 4px 16px rgba(0, 0, 0, 0.5)",
  },
  "warm-academic": {
    bg: "#FAF7F2",
    nodeBg: "#FFFFFF",
    nodeBorder: "rgba(120, 80, 40, 0.1)",
    text: "#2D1B0E",
    textSecondary: "#7C6A58",
    edgeStroke: "rgba(120, 80, 40, 0.18)",
    accent: "#C58A57",
    shadow: "0 2px 16px rgba(120, 80, 40, 0.06)",
  },
}
