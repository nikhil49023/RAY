import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react'
import { useChat } from '@ai-sdk/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Activity, Brain, ChartColumn, FileText, FlaskConical, MessageSquare,
  PanelLeft, PanelLeftClose, Plus, Send, Settings, Square,
  Workflow, X, Zap, TrendingUp, BarChart3, Shield, Globe2, Trash2,
  PieChart, Layers, Radio, Sigma, FunctionSquare, Atom,
} from 'lucide-react'
import { FlowDiagram } from './visual/FlowDiagram'
import { D3Graph } from './visual/D3Graph'
import { IllustrationCard } from './visual/IllustrationCard'
import type { DiagramSpec, GraphSpec, IllustrationSpec } from './visual/types'

/* ═══════════════════════════════════════════════════════════════════
   TYPE DEFINITIONS
   ═══════════════════════════════════════════════════════════════════ */

interface ModelEntry {
  id: string
  label: string
  provider: string
  specialty: string
  description: string
  features: string[]
  is_default?: boolean
}
interface ModelsResponse {
  models?: ModelEntry[] | Record<string, string>
  defaultModel?: string | null
  singleModelMode?: boolean
}
interface ThreadItem { id: string; title: string; updated_at: string; message_count: number }
interface ArtifactItem { id: string; title: string; type: string; created_at: string; preview: string }
interface ResearchItem { id: string; query: string; model: string; created_at: string; source_count: number }
interface EvidenceItem {
  source: string
  title?: string
  url: string
  claim: string
  provider?: string
  relu_score?: number
}
interface ThinkingLogItem {
  node: string
  title: string
  detail: string
  provider?: string
  reranker?: string
  mode?: string
  model?: string
  result_count?: number
}
interface FirecrawlSettings {
  strategy: string
  baseUrl: string
  cloudUrl: string
  fallbackApiKey: string
}
interface UiSettings {
  showThinkingLogs: boolean
  renderVisualsInline: boolean
  researchOutput: string
}
interface AgentRuntimeSettings {
  backend: string
  codexPath: string
  codexModel: string
  codexProviderId: string
  codexBaseUrl: string
  codexSandbox: string
  codexApprovalPolicy: string
}
interface AppSettings {
  temperature?: number
  apiKeys?: { groq?: string; sarvam?: string; openrouter?: string }
  firecrawl?: Partial<FirecrawlSettings>
  ui?: Partial<UiSettings>
  agentRuntime?: Partial<AgentRuntimeSettings>
}
interface ChartSeries {
  label: string
  data: number[]
  color?: string
}
interface ChartSpec {
  type?: string
  title?: string
  labels?: string[]
  series?: ChartSeries[]
  datasets?: ChartSeries[]
}
interface ScorecardMetric {
  label: string
  value: number
  tone?: 'good' | 'warning' | 'critical' | string
}
interface ScorecardSpec {
  title?: string
  score?: number
  maxScore?: number
  verdict?: string
  summary?: string
  metrics?: ScorecardMetric[]
  strengths?: string[]
  gaps?: string[]
}
interface VisualChartSeries {
  name?: string
  color?: string
  values?: number[]
}
interface VisualChartSpec {
  type?: string
  chartType?: 'line' | 'bar' | 'pie' | 'area'
  title?: string
  xAxis?: { label?: string; values?: string[] }
  series?: VisualChartSeries[]
  unit?: string
  source?: string
}
interface VisualScoreboardRow {
  rank?: number
  label?: string
  score?: number
  change?: string
  badge?: string
}
interface VisualScoreboardSpec {
  type?: string
  title?: string
  columns?: string[]
  rows?: VisualScoreboardRow[]
  highlightTop?: number
  source?: string
}
interface VisualTableSpec {
  type?: string
  title?: string
  columns?: string[]
  rows?: string[][]
  highlight?: string
}
interface HeatmapCell {
  row: string
  col: string
  value: number
}
interface HeatmapSpec {
  type?: string
  title?: string
  rows?: string[]
  columns?: string[]
  data?: number[][]
  cells?: HeatmapCell[]
  unit?: string
}
interface DonutSpec {
  type?: string
  title?: string
  labels?: string[]
  values?: number[]
  colors?: string[]
}
interface MathEquationSpec {
  type?: string
  title?: string
  latex?: string
  steps?: string[]
  result?: string
  domain?: string
}
interface PhysicsWaveSpec {
  type?: string
  title?: string
  wavelength?: number
  amplitude?: number
  frequency?: number
  phase?: number
  waveType?: string
}
interface PhysicsFieldSpec {
  type?: string
  title?: string
  fieldType?: string
  charges?: { x: number; y: number; q: number }[]
  strength?: number
}
interface PhysicsSpectrumSpec {
  type?: string
  title?: string
  spectrumType?: string
  bands?: { label: string; start: number; end: number; color: string }[]
  peaks?: { wavelength: number; intensity: number; label?: string }[]
}
interface PhysicsOrbitalSpec {
  type?: string
  title?: string
  n?: number
  l?: number
  m?: number
  electronConfig?: string
}
interface VisualTimelineEvent {
  date?: string
  label?: string
  category?: string
}
interface VisualTimelineSpec {
  type?: string
  title?: string
  events?: VisualTimelineEvent[]
  categories?: Record<string, string>
}
interface NodeGraphNode {
  id: string
  label: string
  group?: string
  weight?: number
}
interface NodeGraphEdge {
  source: string
  target: string
  label?: string
}
interface NodeGraphSpec {
  title?: string
  nodes?: NodeGraphNode[]
  edges?: NodeGraphEdge[]
  groups?: Record<string, string>
}

type SidebarTab = 'history' | 'artifacts' | 'research'
type RenderSegment =
  | { type: 'markdown'; content: string }
  | { type: 'document' | 'canvas'; title: string; content: string }
  | { type: 'chart'; raw: string; chart?: ChartSpec }
  | { type: 'scorecard'; raw: string; scorecard?: ScorecardSpec }
  | { type: 'mermaid'; content: string }
  | { type: 'visual'; visualType: string; raw: string; data?: unknown }
  | { type: 'node-graph'; raw: string; graph?: NodeGraphSpec }
  | { type: 'diagram'; raw: string; spec?: DiagramSpec }
  | { type: 'd3graph'; raw: string; spec?: GraphSpec }
  | { type: 'widget'; tag: string; content: string }
  | { type: 'math-equation'; raw: string; spec?: MathEquationSpec }
  | { type: 'physics-wave'; raw: string; spec?: PhysicsWaveSpec }
  | { type: 'physics-field'; raw: string; spec?: PhysicsFieldSpec }
  | { type: 'physics-spectrum'; raw: string; spec?: PhysicsSpectrumSpec }
  | { type: 'physics-orbital'; raw: string; spec?: PhysicsOrbitalSpec }

const WIDGET_TAGS = [
  'research-panel',
  'node-graph-panel',
  'editorial',
  'cinematic',
  'analysis-panel',
  'report-panel',
  'artifact-panel',
  'data-panel',
  'widget-panel',
  'stepper-panel',
  'cinematic-stepper',
]

const WIDGET_BASE_CSS = `
:root {
  color-scheme: dark;
  --color-text-primary: #eef2f7;
  --color-text-secondary: #c1cad6;
  --color-text-tertiary: #8995a7;
  --color-text-success: #43b78b;
  --color-text-warning: #d1a24b;
  --color-background-primary: #12161d;
  --color-background-secondary: #171c24;
  --color-border-primary: rgba(255, 255, 255, 0.22);
  --color-border-secondary: rgba(255, 255, 255, 0.16);
  --color-border-tertiary: rgba(255, 255, 255, 0.1);
  --font-sans: Inter, system-ui, sans-serif;
  --font-serif: Georgia, 'Times New Roman', serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, monospace;
  --border-radius-md: 8px;
  --border-radius-lg: 12px;
  --border-radius-xl: 16px;
}
*,
*::before,
*::after { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  color: var(--color-text-primary);
  font-family: var(--font-sans);
  line-height: 1.5;
}
body {
  padding: 0;
}
.widget-root {
  width: 100%;
  padding: 18px;
  border-radius: var(--border-radius-lg);
  background: var(--color-background-primary);
  border: 0.5px solid var(--color-border-tertiary);
}
h1, h2, h3 {
  margin: 0 0 12px;
  line-height: 1.2;
  font-weight: 500;
}
h1 { font-size: 1.35rem; }
h2 { font-size: 1.1rem; }
h3 { font-size: 0.95rem; }
p, ul, ol, table, section, article, div {
  margin-top: 0;
}
p { color: var(--color-text-secondary); }
a {
  color: var(--color-text-primary);
  text-decoration: none;
}
button {
  font: inherit;
  color: var(--color-text-primary);
  background: var(--color-background-secondary);
  border: 0.5px solid var(--color-border-secondary);
  border-radius: 999px;
  padding: 8px 12px;
  cursor: pointer;
}
button:hover { border-color: var(--color-border-primary); }
[data-step] {
  opacity: 1;
  max-height: 1000px;
  overflow: hidden;
}
.is-collapsed {
  opacity: 0.58;
  max-height: 72px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 10px 12px;
  border: 0.5px solid var(--color-border-tertiary);
  text-align: left;
}
th {
  color: var(--color-text-primary);
  background: var(--color-background-secondary);
}
code, pre {
  font-family: var(--font-mono);
}
pre {
  white-space: pre-wrap;
  background: var(--color-background-secondary);
  padding: 14px;
  border-radius: var(--border-radius-md);
  overflow: auto;
}
`

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  if (!response.ok) {
    const detail = (await response.text().catch(() => '')).trim()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

function normalizeModelsResponse(payload: ModelsResponse): { models: ModelEntry[]; defaultModel: string | null; singleModelMode: boolean } {
  const rawModels = payload.models
  let models: ModelEntry[] = []

  if (Array.isArray(rawModels)) {
    models = rawModels.map((model, index) => ({
      ...model,
      provider: model.provider || model.id.split('/', 1)[0].toUpperCase(),
      specialty: model.specialty || 'General assistant',
      description: model.description || 'General-purpose chat and task assistance.',
      features: Array.isArray(model.features) ? model.features : ['Chat'],
      is_default: model.is_default ?? index === 0,
    }))
  } else if (rawModels && typeof rawModels === 'object') {
    models = Object.entries(rawModels).map(([id, label], index) => ({
      id,
      label,
      provider: id.split('/', 1)[0].toUpperCase(),
      specialty: 'General assistant',
      description: 'General-purpose chat and task assistance.',
      features: ['Chat'],
      is_default: index === 0,
    }))
  }

  const defaultModel = payload.defaultModel || models.find(model => model.is_default)?.id || models[0]?.id || null
  return {
    models,
    defaultModel,
    singleModelMode: payload.singleModelMode ?? models.length <= 1,
  }
}

/* ═══════════════════════════════════════════════════════════════════
   API LAYER
   ═══════════════════════════════════════════════════════════════════ */

const api = {
  models: () => requestJson<ModelsResponse>(apiUrl('/api/models')),
  threads: () => requestJson<{ threads?: ThreadItem[] }>(apiUrl('/api/threads')),
  thread: (id: string) => requestJson<{ messages?: { role: string; content: string }[] }>(apiUrl(`/api/threads/${id}`)),
  saveThread: (id: string, title: string, messages: { role: string; content: string }[]) =>
    requestJson<{ id: string }>(apiUrl('/api/threads'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, title, messages }),
    }),
  deleteThread: (id: string) => fetch(apiUrl(`/api/threads/${id}`), { method: 'DELETE' }),
  artifacts: () => requestJson<{ artifacts?: ArtifactItem[] }>(apiUrl('/api/artifacts')),
  artifact: (id: string) => requestJson<{ title: string; content: string }>(apiUrl(`/api/artifacts/${id}`)),
  research: () => requestJson<{ sessions?: ResearchItem[] }>(apiUrl('/api/research')),
  researchItem: (id: string) => requestJson<{ query?: string; brief?: string }>(apiUrl(`/api/research/${id}`)),
  settings: () => requestJson<AppSettings>(apiUrl('/api/settings')),
  saveSettings: (settings: object) =>
    requestJson(apiUrl('/api/settings'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),
}

const DEFAULT_FIRECRAWL: FirecrawlSettings = {
  strategy: 'self_hosted_first',
  baseUrl: 'http://localhost:3002',
  cloudUrl: 'https://api.firecrawl.dev',
  fallbackApiKey: '',
}

const DEFAULT_UI: UiSettings = {
  showThinkingLogs: true,
  renderVisualsInline: false,
  researchOutput: 'document',
}

const DEFAULT_AGENT_RUNTIME: AgentRuntimeSettings = {
  backend: 'langgraph',
  codexPath: 'codex',
  codexModel: 'openai/gpt-oss-20b',
  codexProviderId: 'groq',
  codexBaseUrl: 'https://api.groq.com/openai/v1',
  codexSandbox: 'workspace-write',
  codexApprovalPolicy: 'never',
}

/* ── Premium Chart Palette ─────────────────────────────────────── */
const CHART_COLORS = [
  '#2F6F72',
  '#C58A57',
  '#7A9E7E',
  '#7C6FA8',
  '#B95C6B',
  '#4F7A9A',
  '#A88B64',
  '#5E8C84',
]

/* ═══════════════════════════════════════════════════════════════════
   MARKDOWN RENDERER
   ═══════════════════════════════════════════════════════════════════ */

function Md({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children: headingChildren }) => <h1 className="md-h1">{headingChildren}</h1>,
        h2: ({ children: headingChildren }) => <h2 className="md-h2">{headingChildren}</h2>,
        h3: ({ children: headingChildren }) => <h3 className="md-h3">{headingChildren}</h3>,
        p: ({ children: paragraphChildren }) => <p className="md-paragraph">{paragraphChildren}</p>,
        ul: ({ children: listChildren }) => <ul className="md-list">{listChildren}</ul>,
        ol: ({ children: listChildren }) => <ol className="md-list md-list-ordered">{listChildren}</ol>,
        li: ({ children: listItemChildren }) => <li className="md-list-item">{listItemChildren}</li>,
        blockquote: ({ children: quoteChildren }) => <blockquote className="md-callout">{quoteChildren}</blockquote>,
        hr: () => <div className="md-divider" aria-hidden="true" />,
        table: ({ children: tableChildren }) => (
          <div className="md-table-wrap">
            <table>{tableChildren}</table>
          </div>
        ),
        code: ({ className, children: codeChildren, ...props }: any) => {
          const isBlock = className?.startsWith('language-')
          if (isBlock) {
            return <pre><code className={className} {...props}>{codeChildren}</code></pre>
          }
          return <code {...props}>{codeChildren}</code>
        },
      }}
    >
      {children}
    </ReactMarkdown>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SCORECARD & GAUGE COMPONENTS
   ═══════════════════════════════════════════════════════════════════ */

function GaugeDonut({ value, max, label }: { value: number; max: number; label: string }) {
  const radius = 44
  const circumference = 2 * Math.PI * radius
  const ratio = Math.min(value / Math.max(max, 1), 1)
  const offset = circumference - ratio * circumference
  const healthClass = ratio >= 0.7 ? 'health-good' : ratio >= 0.4 ? 'health-warn' : 'health-bad'

  return (
    <div className="gauge-donut">
      <svg viewBox="0 0 120 120">
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00BFA6" />
            <stop offset="50%" stopColor="#64FFDA" />
            <stop offset="100%" stopColor="#FFD700" />
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" r={radius} className="gauge-bg" />
        <circle
          cx="60"
          cy="60"
          r={radius}
          className={`gauge-fill ${healthClass}`}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          stroke="url(#gaugeGrad)"
        />
      </svg>
      <div className="gauge-label">{value}/{max}</div>
    </div>
  )
}

function ResponseMetaRow({
  evidence,
  thinkingLog,
  mode,
}: {
  evidence: EvidenceItem[]
  thinkingLog: ThinkingLogItem[]
  mode: string
}) {
  const sourceCount = evidence.length
  const stepCount = Math.max(thinkingLog.length, 1)
  const providers = [...new Set(evidence.map(e => e.provider).filter(Boolean))].length

  return (
    <div className="response-meta-row">
      <span>{sourceCount} sources</span>
      <span>{researchDepthLabel(mode, stepCount)}</span>
      {providers > 1 && <span>{providers} providers</span>}
    </div>
  )
}

function researchDepthLabel(mode: string, stepCount: number) {
  if (mode === 'reasoning') return `${stepCount || 1} step`
  if (mode === 'research') return 'research'
  return 'direct'
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function createSessionId() {
  return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function prettifyWidgetTag(tag: string) {
  return tag
    .replace(/-/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase())
}

function trailingOpenWidgetStartIndex(content: string) {
  const patterns = [
    /<(?:document|canvas):\s*[^>]*$/i,
    /<visual(?:\s+type="[^"]*")?>[\s\S]*$/i,
    /```(?:chart|scorecard|mermaid)\s*[\s\S]*$/i,
    /<([a-z]+(?:-[a-z]+)+)>[\s\S]*$/i,
  ]
  let candidate = -1
  for (const pattern of patterns) {
    const match = content.match(pattern)
    if (match && typeof match.index === 'number') {
      candidate = Math.max(candidate, match.index)
    }
  }
  return candidate
}

/* ═══════════════════════════════════════════════════════════════════
   CHART & CONTENT PARSING
   ═══════════════════════════════════════════════════════════════════ */

function normalizeChart(input: ChartSpec | undefined): ChartSpec | null {
  if (!input || typeof input !== 'object') return null
  const labels = Array.isArray(input.labels) ? input.labels.map(label => String(label)) : []
  const sourceSeries = Array.isArray(input.series) ? input.series : Array.isArray(input.datasets) ? input.datasets : []
  const series = sourceSeries
    .map((item, idx) => ({
      label: String(item.label || `Series ${idx + 1}`),
      data: Array.isArray(item.data) ? item.data.map(value => Number(value) || 0) : [],
      color: item.color || CHART_COLORS[idx % CHART_COLORS.length],
    }))
    .filter(item => item.data.length > 0)
  if (labels.length === 0 || series.length === 0) return null
  return {
    type: input.type || 'bar',
    title: input.title || 'Chart',
    labels,
    series,
  }
}

function parseJsonBlock<T>(raw: string): T | undefined {
  try {
    return JSON.parse(raw) as T
  } catch {
    return undefined
  }
}

function normalizeVisualChart(input: VisualChartSpec | undefined): ChartSpec | null {
  if (!input || typeof input !== 'object') return null
  const labels = Array.isArray(input.xAxis?.values) ? input.xAxis?.values.map(value => String(value)) : []
  const series = Array.isArray(input.series)
    ? input.series.map((item, index) => ({
      label: String(item.name || `Series ${index + 1}`),
      data: Array.isArray(item.values) ? item.values.map(value => Number(value) || 0) : [],
      color: item.color || CHART_COLORS[index % CHART_COLORS.length],
    }))
    : []
  if (!labels.length || !series.length) return null
  return {
    type: input.chartType || 'bar',
    title: input.title || 'Chart',
    labels,
    series,
  }
}

function isMermaidStartLine(line: string) {
  return /^(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph|quadrantChart|requirementDiagram|C4Context|C4Container|C4Component|C4Dynamic|C4Deployment)\b/.test(line.trim())
}

function isMermaidContinuationLine(line: string) {
  const trimmed = line.trim()
  if (!trimmed) return true
  if (/^(?:%%|style|linkStyle|classDef|class|click|subgraph|end|direction|accTitle|accDescr)\b/.test(trimmed)) return true
  if (/^(?:[A-Za-z0-9_"'()[\]{}.-]+)\s*(?:-->|\-\->|---|==>|-.->|-.|==|:::)/.test(trimmed)) return true
  if (/^\s+/.test(line)) return true
  return false
}

function appendMarkdownSegments(target: RenderSegment[], markdown: string) {
  if (!markdown.trim()) return
  const lines = markdown.split('\n')
  const localSegments: RenderSegment[] = []
  let index = 0
  let markdownBuffer: string[] = []

  const flushMarkdown = () => {
    const block = markdownBuffer.join('\n').trim()
    if (block) localSegments.push({ type: 'markdown', content: block })
    markdownBuffer = []
  }

  while (index < lines.length) {
    const line = lines[index]
    if (!isMermaidStartLine(line)) {
      markdownBuffer.push(line)
      index += 1
      continue
    }

    flushMarkdown()
    const diagramLines = [line]
    index += 1

    while (index < lines.length && isMermaidContinuationLine(lines[index])) {
      diagramLines.push(lines[index])
      index += 1
    }

    const diagram = diagramLines.join('\n').trim()
    if (diagram) {
      localSegments.push({ type: 'mermaid', content: diagram })
    }
  }

  flushMarkdown()

  if (localSegments.length === 0) {
    target.push({ type: 'markdown', content: markdown.trim() })
    return
  }

  target.push(...localSegments)
}

function sanitizeMermaidSource(input: string) {
  return input
    .replace(/\|([^|\n]+)\|>\s+/g, '|$1| ')
    .replace(/\s+>\s+([A-Za-z0-9_[(])/g, ' $1')
    .trim()
}

function parseStructuredContent(content: string): RenderSegment[] {
  if (!content) return []

  const widgetPattern = WIDGET_TAGS.join('|')
  const pattern = new RegExp(
    `<(document|canvas):\\s*(.*?)>([\\s\\S]*?)<\\/(?:document|canvas)>|` +
    '<visual\\s+type="([^"]+)">([\\s\\S]*?)<\\/visual>|' +
    '<node-graph>([\\s\\S]*?)<\\/node-graph>|' +
    '```(chart|scorecard|mermaid)\\s*([\\s\\S]*?)```|' +
    `<(${widgetPattern})>([\\s\\S]*?)<\\/\\9>`,
    'gi',
  )
  const segments: RenderSegment[] = []
  let lastIndex = 0

  for (const match of content.matchAll(pattern)) {
    const start = match.index ?? 0
    if (start > lastIndex) {
      const markdown = content.slice(lastIndex, start)
      appendMarkdownSegments(segments, markdown)
    }

    const blockType = match[1]?.toLowerCase()
    const title = match[2]?.trim()
    const body = match[3]?.trim()
    const visualType = match[4]?.toLowerCase()
    const visualBody = match[5]?.trim() || ''
    const nodeGraphBody = match[6]?.trim() || ''
    const fenceType = match[7]?.toLowerCase()
    const fenceBody = match[8]?.trim() || ''
    const widgetTag = match[9]?.toLowerCase()
    const widgetBody = match[10]?.trim() || ''

    if (blockType === 'document' || blockType === 'canvas') {
      segments.push({
        type: blockType,
        title: title || (blockType === 'document' ? 'Document' : 'Canvas'),
        content: body || '',
      })
    } else if (visualType) {
      if (visualType === 'diagram') {
        segments.push({
          type: 'diagram',
          raw: visualBody,
          spec: parseJsonBlock<DiagramSpec>(visualBody),
        })
      } else if (visualType === 'graph') {
        segments.push({
          type: 'd3graph',
          raw: visualBody,
          spec: parseJsonBlock<GraphSpec>(visualBody),
        })
      } else {
        segments.push({
          type: 'visual',
          visualType,
          raw: visualBody,
          data: parseJsonBlock(visualBody),
        })
      }
    } else if (nodeGraphBody) {
      segments.push({
        type: 'node-graph',
        raw: nodeGraphBody,
        graph: parseJsonBlock<NodeGraphSpec>(nodeGraphBody),
      })
    } else if (fenceType === 'chart' || fenceType === 'scorecard') {
      let parsed: ChartSpec | ScorecardSpec | undefined
      try {
        parsed = JSON.parse(fenceBody) as ChartSpec | ScorecardSpec
      } catch {
        parsed = undefined
      }
      if (fenceType === 'chart') {
        segments.push({ type: 'chart', raw: fenceBody, chart: parsed as ChartSpec | undefined })
      } else {
        segments.push({ type: 'scorecard', raw: fenceBody, scorecard: parsed as ScorecardSpec | undefined })
      }
    } else if (fenceType === 'mermaid') {
      segments.push({ type: 'mermaid', content: fenceBody })
    } else if (widgetTag) {
      segments.push({ type: 'widget', tag: widgetTag, content: widgetBody })
    }

    lastIndex = start + match[0].length
  }

  if (lastIndex < content.length) {
    let markdown = content.slice(lastIndex)
    const openStart = trailingOpenWidgetStartIndex(markdown)
    if (openStart >= 0) {
      markdown = markdown.slice(0, openStart)
    }
    appendMarkdownSegments(segments, markdown)
  }

  return segments.length > 0 ? segments : [{ type: 'markdown', content }]
}

function VisualTableCard({ spec, raw }: { spec?: VisualTableSpec; raw: string }) {
  if (!spec || !Array.isArray(spec.columns) || !Array.isArray(spec.rows)) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><BarChart3 size={13} /> Table Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card visual-table-card">
      <div className="structured-card-header">
        <span className="structured-pill"><BarChart3 size={13} /> Table</span>
        <h4>{spec.title || 'Comparison'}</h4>
      </div>
      <div className="visual-table-wrap">
        <table className="visual-table">
          <thead>
            <tr>
              {spec.columns.map(column => <th key={column}>{column}</th>)}
            </tr>
          </thead>
          <tbody>
            {spec.rows.map((row, index) => (
              <tr key={`${row.join('-')}-${index}`}>
                {row.map((cell, cellIndex) => (
                  <td
                    key={`${cell}-${cellIndex}`}
                    className={typeof spec.highlight === 'string' && cell === spec.highlight ? 'is-highlight' : ''}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function VisualTimelineCard({ spec, raw }: { spec?: VisualTimelineSpec; raw: string }) {
  const events = Array.isArray(spec?.events) ? spec?.events : []
  if (!spec || !events.length) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><Workflow size={13} /> Timeline Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card visual-timeline-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Workflow size={13} /> Timeline</span>
        <h4>{spec.title || 'Timeline'}</h4>
      </div>
      <div className="visual-timeline">
        {events.map((event, index) => (
          <div key={`${event.date}-${event.label}-${index}`} className="visual-timeline-item">
            <div className="visual-timeline-rail">
              <span className="visual-timeline-dot" />
              {index < events.length - 1 && <span className="visual-timeline-line" />}
            </div>
            <div className="visual-timeline-copy">
              <span className="visual-timeline-date">{event.date}</span>
              <strong>{event.label}</strong>
              {event.category && <span>{event.category}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function VisualScoreboardCard({ spec, raw }: { spec?: VisualScoreboardSpec; raw: string }) {
  const rows = Array.isArray(spec?.rows) ? spec.rows : []
  if (!spec || !rows.length) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><TrendingUp size={13} /> Scoreboard Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card visual-scoreboard-card">
      <div className="structured-card-header">
        <span className="structured-pill"><TrendingUp size={13} /> Scoreboard</span>
        <h4>{spec.title || 'Ranking'}</h4>
      </div>
      <div className="visual-scoreboard-list">
        {rows.map((row, index) => (
          <div
            key={`${row.label}-${index}`}
            className={`visual-scoreboard-row ${index < (spec.highlightTop || 0) ? 'is-top' : ''}`}
          >
            <span className="visual-scoreboard-rank">{row.badge || row.rank || index + 1}</span>
            <span className="visual-scoreboard-label">{row.label || `Entry ${index + 1}`}</span>
            <span className="visual-scoreboard-score">{typeof row.score === 'number' ? row.score : '—'}</span>
            <span className="visual-scoreboard-change">{row.change || ''}</span>
          </div>
        ))}
      </div>
      {spec.source && <div className="visual-footnote">{spec.source}</div>}
    </div>
  )
}

function NodeGraphCard({ graph, raw, onPrompt }: { graph?: NodeGraphSpec; raw: string; onPrompt?: (text: string) => void }) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph?.edges) ? graph.edges : []
  const palette = graph?.groups || {
    framework: '#1D9E75',
    concept: '#7F77DD',
    source: '#D85A30',
  }

  if (!graph || !nodes.length) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><Workflow size={13} /> Node Graph Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const positions = nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1)
    const radius = 115 + ((node.weight || 1) - 1) * 12
    return {
      ...node,
      x: 190 + Math.cos(angle) * radius,
      y: 150 + Math.sin(angle) * radius * 0.68,
      r: node.weight === 3 ? 32 : node.weight === 2 ? 24 : 18,
      color: palette[node.group || 'concept'] || '#7F77DD',
    }
  })

  const positionMap = new Map(positions.map(node => [node.id, node]))

  return (
    <div className="structured-card node-graph-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Workflow size={13} /> Graph</span>
        <h4>{graph.title || 'Concept map'}</h4>
      </div>
      <svg className="node-graph-svg" viewBox="0 0 380 300" role="img" aria-label={graph.title || 'Concept graph'}>
        {edges.map((edge, index) => {
          const source = positionMap.get(edge.source)
          const target = positionMap.get(edge.target)
          if (!source || !target) return null
          return (
            <line
              key={`${edge.source}-${edge.target}-${index}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              className="node-graph-edge"
            />
          )
        })}
        {positions.map(node => (
          <g
            key={node.id}
            className="node-graph-node"
            onClick={() => onPrompt?.(`Tell me more about ${node.label}`)}
            role={onPrompt ? 'button' : undefined}
            tabIndex={onPrompt ? 0 : -1}
            onKeyDown={event => {
              if ((event.key === 'Enter' || event.key === ' ') && onPrompt) {
                event.preventDefault()
                onPrompt(`Tell me more about ${node.label}`)
              }
            }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.r}
              fill={`${node.color}24`}
              stroke={node.color}
              strokeWidth="1.5"
            />
            <text x={node.x} y={node.y + 4} textAnchor="middle" className="node-graph-label">
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function EmbeddedWidget({ tag, content }: { tag: string; content: string }) {
  const iframeIdRef = useRef(`widget-${Math.random().toString(36).slice(2)}`)
  const [height, setHeight] = useState(320)

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const payload = event.data
      if (!payload || typeof payload !== 'object') return
      if (payload.type !== 'widget-height' || payload.widgetId !== iframeIdRef.current) return
      const nextHeight = Number(payload.height) || 320
      setHeight(Math.max(220, Math.min(nextHeight + 8, 2400)))
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  const srcDoc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>${WIDGET_BASE_CSS}</style>
</head>
<body>
  <div class="widget-root widget-${tag}">${content}</div>
  <script>
    const widgetId = ${JSON.stringify(iframeIdRef.current)};
    function notifyHeight() {
      const height = Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight
      );
      window.parent.postMessage({ type: 'widget-height', widgetId, height }, '*');
    }
    window.sendPrompt = function(text) {
      if (!text) return;
      window.parent.postMessage({ type: 'send-prompt', text: String(text) }, '*');
    };
    document.addEventListener('click', function(event) {
      const target = event.target.closest('[data-send-prompt]');
      if (!target) return;
      event.preventDefault();
      window.sendPrompt(target.getAttribute('data-send-prompt'));
    });
    window.addEventListener('load', function() {
      notifyHeight();
      requestAnimationFrame(notifyHeight);
      setTimeout(notifyHeight, 60);
    });
    new MutationObserver(notifyHeight).observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
  </script>
</body>
</html>`

  return (
    <div className="embedded-widget">
      <div className="structured-card-header">
        <span className="structured-pill"><Workflow size={13} /> Widget</span>
        <h4>{prettifyWidgetTag(tag)}</h4>
      </div>
      <iframe
        className="embedded-widget-frame"
        title={prettifyWidgetTag(tag)}
        srcDoc={srcDoc}
        sandbox="allow-scripts allow-same-origin"
        style={{ height }}
      />
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   MERMAID CARD
   ═══════════════════════════════════════════════════════════════════ */

function MermaidCard({ content }: { content: string }) {
  const iframeIdRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`)
  const [height, setHeight] = useState(340)

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const payload = event.data
      if (!payload || typeof payload !== 'object') return
      if (payload.type !== 'widget-height' || payload.widgetId !== iframeIdRef.current) return
      const nextHeight = Number(payload.height) || 340
      setHeight(Math.max(240, Math.min(nextHeight + 8, 2200)))
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  const sanitizedContent = sanitizeMermaidSource(content)
  const srcDoc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>${WIDGET_BASE_CSS}
  .widget-root { padding: 14px; }
  .mermaid-shell {
    padding: 14px;
    border-radius: var(--border-radius-md);
    background: linear-gradient(180deg, rgba(23, 28, 36, 0.94), rgba(18, 22, 29, 0.98));
    border: 0.5px solid rgba(255, 255, 255, 0.12);
  }
  .mermaid {
    display: flex;
    justify-content: center;
  }
  svg { max-width: 100%; height: auto; }
  </style>
</head>
<body>
  <div class="widget-root mermaid-shell">
    <div class="mermaid">${sanitizedContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
  </div>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    const widgetId = ${JSON.stringify(iframeIdRef.current)};
    const notifyHeight = () => {
      const height = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
      window.parent.postMessage({ type: 'widget-height', widgetId, height }, '*');
    };
    const run = async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'base',
          themeVariables: {
            primaryColor: '#1d2430',
            primaryTextColor: '#eef2f7',
            primaryBorderColor: '#5e8c84',
            lineColor: '#8fa2b6',
            secondaryColor: '#151a22',
            tertiaryColor: '#171d27',
            background: '#12161d',
            mainBkg: '#1a212d',
            nodeBorder: '#6b8da2',
            clusterBkg: '#151d28',
            clusterBorder: '#65708a',
            edgeLabelBackground: '#12161d',
            fontFamily: 'Inter, system-ui, sans-serif',
            tertiaryTextColor: '#d9e2ef',
          },
        });
        await mermaid.run({ querySelector: '.mermaid' });
      } catch (error) {
        console.error(error);
      }
      notifyHeight();
      requestAnimationFrame(notifyHeight);
      setTimeout(notifyHeight, 80);
    };
    window.addEventListener('load', run);
    new MutationObserver(notifyHeight).observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
  </script>
</body>
</html>`

  return (
    <div className="structured-card mermaid-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Workflow size={13} /> Diagram</span>
      </div>
      <iframe
        className="embedded-widget-frame"
        title="Mermaid diagram"
        srcDoc={srcDoc}
        sandbox="allow-scripts allow-same-origin"
        style={{ height }}
      />
    </div>
  )
}

function ScorecardBlock({ scorecard, raw }: { scorecard?: ScorecardSpec; raw: string }) {
  const metrics = Array.isArray(scorecard?.metrics) ? scorecard?.metrics : []
  const strengths = Array.isArray(scorecard?.strengths) ? scorecard?.strengths : []
  const gaps = Array.isArray(scorecard?.gaps) ? scorecard?.gaps : []
  const score = typeof scorecard?.score === 'number' ? scorecard.score : null
  const maxScore = typeof scorecard?.maxScore === 'number' && scorecard.maxScore > 0 ? scorecard.maxScore : 100

  if (!scorecard || score === null) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><BarChart3 size={13} /> Scorecard Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card scorecard-block">
      <div className="scorecard-shell">
        <div className="scorecard-topline" />
        <div className="scorecard-header">
          <div className="scorecard-copy">
            <span className="section-kicker">{scorecard.title || 'Assessment'}</span>
            <p>{scorecard.summary || 'Structured evaluation generated in visual mode.'}</p>
          </div>
        </div>
        <div className="scorecard-hero">
          <div className="scorecard-total">
            <span className="scorecard-total-value">{score}</span>
            <span className="scorecard-total-max">/{maxScore}</span>
          </div>
          <div className="scorecard-verdict">
            <strong>{scorecard.verdict || 'Assessment'}</strong>
          </div>
        </div>

        {metrics.length > 0 && (
          <div className="scorecard-metrics">
            {metrics.map(metric => {
              const safeValue = Math.max(0, Math.min(metric.value, maxScore))
              return (
                <div key={metric.label} className="scorecard-metric-row">
                  <div className="scorecard-metric-head">
                    <span>{metric.label}</span>
                    <span>{safeValue}</span>
                  </div>
                  <div className="scorecard-metric-track">
                    <div
                      className={`scorecard-metric-fill ${metric.tone || 'good'}`}
                      style={{ width: `${(safeValue / maxScore) * 100}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="scorecard-columns">
          {strengths.length > 0 && (
            <div className="scorecard-section">
              <h4>What&apos;s Working</h4>
              <ul>
                {strengths.map(item => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}
          {gaps.length > 0 && (
            <div className="scorecard-section">
              <h4>Critical Gaps</h4>
              <ul className="critical">
                {gaps.map(item => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   CHART CARD — Vibrant Colorful SVG Rendering
   ═══════════════════════════════════════════════════════════════════ */

function ChartCard({ chart, raw }: { chart?: ChartSpec; raw: string }) {
  const normalized = normalizeChart(chart)
  if (!normalized) {
    return (
      <div className="structured-card chart-card">
        <div className="structured-card-header">
          <span className="structured-pill"><ChartColumn size={13} /> Chart Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const chartType = normalized.type || 'bar'
  const labels = normalized.labels || []
  const series = normalized.series || []
  const values = series.flatMap(item => item.data)
  const maxValue = Math.max(...values, 1)
  const width = 680
  const height = 300
  const padding = { top: 28, right: 20, bottom: 52, left: 50 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const linePoints = (data: number[]) =>
    data
      .map((value, index) => {
        const x = padding.left + ((index / Math.max(labels.length - 1, 1)) * chartWidth)
        const y = padding.top + chartHeight - ((value / maxValue) * chartHeight)
        return `${x},${y}`
      })
      .join(' ')

  const areaPath = (data: number[]) => {
    if (data.length < 2) return ''
    const points = data.map((value, index) => {
      const x = padding.left + ((index / Math.max(labels.length - 1, 1)) * chartWidth)
      const y = padding.top + chartHeight - ((value / maxValue) * chartHeight)
      return { x, y }
    })
    let path = `M ${points[0].x},${points[0].y}`
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1]
      const curr = points[i]
      const cpx1 = prev.x + (curr.x - prev.x) / 3
      const cpx2 = curr.x - (curr.x - prev.x) / 3
      path += ` C ${cpx1},${prev.y} ${cpx2},${curr.y} ${curr.x},${curr.y}`
    }
    path += ` L ${points[points.length - 1].x},${padding.top + chartHeight} L ${points[0].x},${padding.top + chartHeight} Z`
    return path
  }

  if (chartType === 'pie') {
    const total = series.reduce((sum, s) => sum + s.data.reduce((a, b) => a + b, 0), 0) || 1
    const cx = width / 2
    const cy = height / 2
    const radius = Math.min(width, height) / 2 - 40
    let cumulativeAngle = -90

    return (
      <div className="structured-card chart-card">
        <div className="structured-card-header">
          <span className="structured-pill"><PieChart size={13} /> Pie Chart</span>
          <h4>{normalized.title}</h4>
        </div>
        <div className="chart-legend">
          {series.map((item, index) => (
            <div key={item.label} className="legend-item">
              <span
                className="legend-swatch"
                style={{ '--swatch': item.color || CHART_COLORS[index % CHART_COLORS.length] } as CSSProperties}
              />
              <span>{item.label}: {item.data.reduce((a, b) => a + b, 0)}</span>
            </div>
          ))}
        </div>
        <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={normalized.title}>
          {series.map((item, index) => {
            const value = item.data.reduce((a, b) => a + b, 0)
            const angle = (value / total) * 360
            const startAngle = cumulativeAngle
            const endAngle = cumulativeAngle + angle
            cumulativeAngle = endAngle

            if (angle < 0.5) return null

            const startRad = (startAngle * Math.PI) / 180
            const endRad = (endAngle * Math.PI) / 180
            const x1 = cx + radius * Math.cos(startRad)
            const y1 = cy + radius * Math.sin(startRad)
            const x2 = cx + radius * Math.cos(endRad)
            const y2 = cy + radius * Math.sin(endRad)
            const largeArc = angle > 180 ? 1 : 0
            const color = item.color || CHART_COLORS[index % CHART_COLORS.length]

            return (
              <path
                key={item.label}
                d={`M ${cx},${cy} L ${x1},${y1} A ${radius},${radius} 0 ${largeArc} 1 ${x2},${y2} Z`}
                fill={color}
                stroke="#080418"
                strokeWidth="2"
              />
            )
          })}
          <circle cx={cx} cy={cy} r={radius * 0.45} fill="#12161d" />
          <text x={cx} y={cy - 6} textAnchor="middle" fill="#eef2f7" fontSize="18" fontWeight="700" fontFamily="var(--font)">
            {total}
          </text>
          <text x={cx} y={cy + 14} textAnchor="middle" fill="#8B949E" fontSize="11" fontFamily="var(--mono)">
            Total
          </text>
        </svg>
      </div>
    )
  }

  return (
    <div className="structured-card chart-card">
      <div className="structured-card-header">
        <span className="structured-pill"><BarChart3 size={13} /> Visual Render</span>
        <h4>{normalized.title}</h4>
      </div>
      <div className="chart-legend">
        {series.map((item, index) => (
          <div key={item.label} className="legend-item">
            <span
              className="legend-swatch"
              style={{ '--swatch': item.color || CHART_COLORS[index % CHART_COLORS.length] } as CSSProperties}
            />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
      <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={normalized.title}>
        <defs>
          {series.map((item, idx) => {
            const color = item.color || CHART_COLORS[idx % CHART_COLORS.length]
            return (
              <linearGradient key={`grad-${idx}`} id={`chartGrad${idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity="1" />
                <stop offset="100%" stopColor={color} stopOpacity="0.6" />
              </linearGradient>
            )
          })}
          {series.map((item, idx) => {
            const color = item.color || CHART_COLORS[idx % CHART_COLORS.length]
            return (
              <linearGradient key={`areaGrad-${idx}`} id={`areaGrad${idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity="0.35" />
                <stop offset="100%" stopColor={color} stopOpacity="0.02" />
              </linearGradient>
            )
          })}
        </defs>

        {[0, 0.25, 0.5, 0.75, 1].map(step => {
          const y = padding.top + chartHeight - (chartHeight * step)
          const value = Math.round(maxValue * step)
          return (
            <g key={step}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="chart-grid-line" />
              <text x={padding.left - 12} y={y + 4} className="chart-axis-text" textAnchor="end">{value}</text>
            </g>
          )
        })}

        {chartType === 'area'
          ? series.map((item, index) => {
            const color = item.color || CHART_COLORS[index % CHART_COLORS.length]
            return (
              <g key={item.label}>
                <path
                  d={areaPath(item.data)}
                  fill={`url(#areaGrad${index})`}
                />
                <polyline
                  fill="none"
                  stroke={color}
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={linePoints(item.data)}
                />
                {item.data.map((value, valueIndex) => {
                  const x = padding.left + ((valueIndex / Math.max(labels.length - 1, 1)) * chartWidth)
                  const y = padding.top + chartHeight - ((value / maxValue) * chartHeight)
                  return (
                    <circle
                      key={`${item.label}-${valueIndex}`}
                      cx={x}
                      cy={y}
                      r="4"
                      fill={color}
                      stroke="#080418"
                      strokeWidth="2"
                    />
                  )
                })}
              </g>
            )
          })
          : chartType === 'line'
            ? series.map((item, index) => {
              const color = item.color || CHART_COLORS[index % CHART_COLORS.length]
              return (
                <g key={item.label}>
                  <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="3"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    points={linePoints(item.data)}
                  />
                  {item.data.map((value, valueIndex) => {
                    const x = padding.left + ((valueIndex / Math.max(labels.length - 1, 1)) * chartWidth)
                    const y = padding.top + chartHeight - ((value / maxValue) * chartHeight)
                    return (
                      <circle
                        key={`${item.label}-${valueIndex}`}
                        cx={x}
                        cy={y}
                        r="5"
                        fill={color}
                        stroke="#080418"
                        strokeWidth="2"
                      />
                    )
                  })}
                </g>
              )
            })
            : labels.map((label, labelIndex) => {
              const groupWidth = chartWidth / Math.max(labels.length, 1)
              const innerWidth = groupWidth * 0.8
              const barWidth = innerWidth / Math.max(series.length, 1)
              return (
                <g key={label}>
                  {series.map((item, seriesIndex) => {
                    const value = item.data[labelIndex] || 0
                    const barHeight = (value / maxValue) * chartHeight
                    const x = padding.left + (groupWidth * labelIndex) + (groupWidth - innerWidth) / 2 + (barWidth * seriesIndex)
                    const y = padding.top + chartHeight - barHeight
                    return (
                      <rect
                        key={`${label}-${item.label}`}
                        x={x}
                        y={y}
                        width={Math.max(barWidth - 4, 12)}
                        height={barHeight}
                        rx="6"
                        fill={`url(#chartGrad${seriesIndex})`}
                      />
                    )
                  })}
                </g>
              )
            })}

        {labels.map((label, index) => {
          const x = padding.left + ((index + 0.5) * (chartWidth / Math.max(labels.length, 1)))
          return (
            <text key={label} x={x} y={height - 14} textAnchor="middle" className="chart-axis-text chart-axis-label">
              {label.length > 12 ? label.slice(0, 12) + '…' : label}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

function HeatmapCard({ spec, raw }: { spec?: HeatmapSpec; raw: string }) {
  const rows = Array.isArray(spec?.rows) ? spec.rows : []
  const columns = Array.isArray(spec?.columns) ? spec.columns : []
  const data = Array.isArray(spec?.data) ? spec.data : []

  if (!spec || !rows.length || !columns.length || !data.length) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><Layers size={13} /> Heatmap Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const values = data.flat()
  const min = Math.min(...values)
  const max = Math.max(...values, 1)
  const scale = Math.max(max - min, 1)
  const unit = spec.unit ? ` ${spec.unit}` : ''

  const colorFor = (value: number) => {
    const t = (value - min) / scale
    return `rgba(0, 191, 166, ${0.12 + t * 0.7})`
  }

  return (
    <div className="structured-card heatmap-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Layers size={13} /> Heatmap</span>
        <h4>{spec.title || 'Heatmap'}</h4>
      </div>
      <div className="heatmap-grid-wrap">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th> </th>
              {columns.map(col => <th key={col}>{col}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row}>
                <th>{row}</th>
                {columns.map((col, colIndex) => {
                  const value = Number(data[rowIndex]?.[colIndex] ?? 0)
                  return (
                    <td key={`${row}-${col}`} style={{ background: colorFor(value) }}>
                      <span title={`${row} × ${col}: ${value}${unit}`}>{value}</span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DonutChartCard({ spec, raw }: { spec?: DonutSpec; raw: string }) {
  const labels = Array.isArray(spec?.labels) ? spec.labels : []
  const values = Array.isArray(spec?.values) ? spec.values : []
  const colors = Array.isArray(spec?.colors) && spec.colors.length ? spec.colors : CHART_COLORS

  if (!spec || !labels.length || !values.length || labels.length !== values.length) {
    return (
      <div className="structured-card scorecard-block">
        <div className="structured-card-header">
          <span className="structured-pill"><Radio size={13} /> Donut Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const total = values.reduce((acc, value) => acc + value, 0) || 1
  const size = 240
  const radius = 92
  const hole = 56
  const center = size / 2
  let angleStart = -90

  const segmentPath = (start: number, end: number) => {
    const startOuter = (start * Math.PI) / 180
    const endOuter = (end * Math.PI) / 180
    const x1 = center + radius * Math.cos(startOuter)
    const y1 = center + radius * Math.sin(startOuter)
    const x2 = center + radius * Math.cos(endOuter)
    const y2 = center + radius * Math.sin(endOuter)
    const xi1 = center + hole * Math.cos(endOuter)
    const yi1 = center + hole * Math.sin(endOuter)
    const xi2 = center + hole * Math.cos(startOuter)
    const yi2 = center + hole * Math.sin(startOuter)
    const largeArc = end - start > 180 ? 1 : 0
    return `M ${x1},${y1} A ${radius},${radius} 0 ${largeArc} 1 ${x2},${y2} L ${xi1},${yi1} A ${hole},${hole} 0 ${largeArc} 0 ${xi2},${yi2} Z`
  }

  return (
    <div className="structured-card donut-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Radio size={13} /> Donut</span>
        <h4>{spec.title || 'Distribution'}</h4>
      </div>
      <div className="donut-layout">
        <svg className="donut-svg" viewBox={`0 0 ${size} ${size}`} role="img" aria-label={spec.title || 'Donut chart'}>
          {labels.map((label, index) => {
            const span = (values[index] / total) * 360
            const start = angleStart
            const end = angleStart + span
            angleStart = end
            return (
              <path
                key={label}
                d={segmentPath(start, end)}
                fill={colors[index % colors.length]}
                stroke="#080418"
                strokeWidth="2"
              />
            )
          })}
          <text x={center} y={center - 4} textAnchor="middle" className="donut-total">{total}</text>
          <text x={center} y={center + 16} textAnchor="middle" className="donut-total-label">total</text>
        </svg>
        <div className="donut-legend-list">
          {labels.map((label, index) => {
            const pct = ((values[index] / total) * 100).toFixed(1)
            return (
              <div key={label} className="donut-legend-item">
                <span className="donut-swatch" style={{ background: colors[index % colors.length] }} />
                <span className="donut-label">{label}</span>
                <span className="donut-value">{values[index]} ({pct}%)</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function MathEquationCard({ spec, raw }: { spec?: MathEquationSpec; raw: string }) {
  const latex = spec?.latex || ''
  const steps = Array.isArray(spec?.steps) ? spec.steps : []
  const result = spec?.result || ''
  const domain = spec?.domain || ''

  if (!spec || !latex) {
    return (
      <div className="structured-card math-card">
        <div className="structured-card-header">
          <span className="structured-pill"><Sigma size={13} /> Math Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  return (
    <div className="structured-card math-card">
      <div className="structured-card-header">
        <span className="structured-pill"><FunctionSquare size={13} /> Equation</span>
        <h4>{spec.title || 'Mathematical Expression'}</h4>
      </div>
      <div className="math-equation-display">
        <div className="math-latex" data-latex={latex} />
        {result && <div className="math-result"><span className="math-result-label">Result</span><span className="math-result-value">{result}</span></div>}
        {domain && <div className="math-domain"><span className="math-domain-label">Domain</span><code>{domain}</code></div>}
      </div>
      {steps.length > 0 && (
        <div className="math-steps">
          <div className="math-steps-title">Solution Steps</div>
          <ol className="math-steps-list">
            {steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

function PhysicsWaveCard({ spec, raw }: { spec?: PhysicsWaveSpec; raw: string }) {
  const wavelength = typeof spec?.wavelength === 'number' ? spec.wavelength : 2
  const amplitude = typeof spec?.amplitude === 'number' ? spec.amplitude : 1
  const frequency = typeof spec?.frequency === 'number' ? spec.frequency : 1
  const phase = typeof spec?.phase === 'number' ? spec.phase : 0
  const waveType = spec?.waveType || 'sine'

  if (!spec) {
    return (
      <div className="structured-card physics-card">
        <div className="structured-card-header">
          <span className="structured-pill"><Atom size={13} /> Wave Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const width = 680
  const height = 280
  const padding = { top: 30, right: 30, bottom: 40, left: 50 }
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const waveFn = (x: number) => {
    const k = (2 * Math.PI) / wavelength
    const omega = 2 * Math.PI * frequency
    const val = amplitude * Math.sin(k * x - omega * 0 + phase)
    return padding.top + chartH / 2 - (val / (amplitude * 1.2)) * (chartH / 2)
  }

  let pathD = `M ${padding.left},${waveFn(0)}`
  for (let i = 1; i <= chartW; i++) {
    const x = (i / chartW) * wavelength * 4
    const y = waveFn(x)
    pathD += ` L ${padding.left + i},${y}`
  }

  const envelopeTop: number[] = []
  const envelopeBot: number[] = []
  for (let i = 0; i <= chartW; i++) {
    const x = (i / chartW) * wavelength * 4
    const norm = x / (wavelength * 4)
    const env = amplitude * Math.exp(-0.5 * Math.pow((norm - 0.5) * 4, 2))
    envelopeTop.push(padding.top + chartH / 2 - (env / (amplitude * 1.2)) * (chartH / 2))
    envelopeBot.push(padding.top + chartH / 2 + (env / (amplitude * 1.2)) * (chartH / 2))
  }

  let envelopePath = `M ${padding.left},${envelopeTop[0]}`
  for (let i = 1; i <= chartW; i++) {
    envelopePath += ` L ${padding.left + i},${envelopeTop[i]}`
  }
  for (let i = chartW; i >= 0; i--) {
    envelopePath += ` L ${padding.left + i},${envelopeBot[i]}`
  }
  envelopePath += ' Z'

  return (
    <div className="structured-card physics-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Atom size={13} /> Wave</span>
        <h4>{spec.title || 'Wave Visualization'}</h4>
      </div>
      <div className="physics-params">
        <span className="physics-param">λ = {wavelength}</span>
        <span className="physics-param">A = {amplitude}</span>
        <span className="physics-param">f = {frequency}</span>
        <span className="physics-param">φ = {phase}°</span>
        <span className="physics-param">{waveType}</span>
      </div>
      <svg className="physics-svg" viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id="waveGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#2F6F72" />
            <stop offset="50%" stopColor="#7A9E7E" />
            <stop offset="100%" stopColor="#4F7A9A" />
          </linearGradient>
          <linearGradient id="envelopeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7A9E7E" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#7A9E7E" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <line x1={padding.left} y1={padding.top + chartH / 2} x2={width - padding.right} y2={padding.top + chartH / 2} className="physics-axis" />
        <path d={envelopePath} fill="url(#envelopeGrad)" />
        <path d={pathD} fill="none" stroke="url(#waveGrad)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {[0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4].map(n => {
          const x = padding.left + (n / 4) * chartW
          return (
            <g key={n}>
              <line x1={x} y1={padding.top} x2={x} y2={padding.top + chartH} className="physics-grid-line" />
              <text x={x} y={height - 10} textAnchor="middle" className="physics-axis-text">{(n * wavelength).toFixed(1)}</text>
            </g>
          )
        })}
        <text x={14} y={padding.top + chartH / 2 + 4} className="physics-axis-text" textAnchor="middle">0</text>
        <text x={14} y={padding.top + 14} className="physics-axis-text" textAnchor="middle">+A</text>
        <text x={14} y={padding.top + chartH + 4} className="physics-axis-text" textAnchor="middle">−A</text>
      </svg>
    </div>
  )
}

function PhysicsFieldCard({ spec, raw }: { spec?: PhysicsFieldSpec; raw: string }) {
  const charges = Array.isArray(spec?.charges) ? spec.charges : []
  const fieldType = spec?.fieldType || 'electric'

  if (!spec || charges.length === 0) {
    return (
      <div className="structured-card physics-card">
        <div className="structured-card-header">
          <span className="structured-pill"><Atom size={13} /> Field Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const size = 400
  const cx = size / 2
  const cy = size / 2

  const fieldLines: string[] = []
  for (const charge of charges) {
    const px = cx + charge.x * size * 0.35
    const py = cy - charge.y * size * 0.35
    const q = charge.q
    const numLines = Math.min(Math.abs(q) * 6, 18)
    const direction = q > 0 ? 1 : -1

    for (let i = 0; i < numLines; i++) {
      const angle = (i / numLines) * 2 * Math.PI
      let x = px
      let y = py
      let path = `M ${x},${y}`
      const step = 4
      const maxSteps = 80

      for (let s = 0; s < maxSteps; s++) {
        let fx = 0
        let fy = 0
        for (const c of charges) {
          const cpx = cx + c.x * size * 0.35
          const cpy = cy - c.y * size * 0.35
          const dx = x - cpx
          const dy = y - cpy
          const r2 = dx * dx + dy * dy
          if (r2 < 100) continue
          const r = Math.sqrt(r2)
          fx += (c.q * dx) / (r2 * r)
          fy += (c.q * dy) / (r2 * r)
        }
        const fMag = Math.sqrt(fx * fx + fy * fy)
        if (fMag < 1e-10) break
        x += direction * (fx / fMag) * step
        y += direction * (fy / fMag) * step
        if (x < 10 || x > size - 10 || y < 10 || y > size - 10) break
        path += ` L ${x},${y}`
      }
      fieldLines.push(path)
    }
  }

  return (
    <div className="structured-card physics-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Atom size={13} /> {fieldType} Field</span>
        <h4>{spec.title || 'Field Lines'}</h4>
      </div>
      <svg className="field-svg" viewBox={`0 0 ${size} ${size}`}>
        <rect width={size} height={size} fill="#0e0c1a" rx="8" />
        {fieldLines.map((path, i) => (
          <path key={i} d={path} fill="none" stroke="#4F7A9A" strokeWidth="1.2" opacity="0.7" strokeLinecap="round" />
        ))}
        {charges.map((charge, i) => {
          const px = cx + charge.x * size * 0.35
          const py = cy - charge.y * size * 0.35
          const isPositive = charge.q > 0
          return (
            <g key={i}>
              <circle cx={px} cy={py} r="14" fill={isPositive ? '#B95C6B' : '#2F6F72'} stroke="#0e0c1a" strokeWidth="2" />
              <text x={px} y={py + 5} textAnchor="middle" fill="#eef2f7" fontSize="14" fontWeight="700" fontFamily="var(--mono)">
                {isPositive ? '+' : '−'}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function PhysicsSpectrumCard({ spec, raw }: { spec?: PhysicsSpectrumSpec; raw: string }) {
  const bands = Array.isArray(spec?.bands) ? spec.bands : []
  const peaks = Array.isArray(spec?.peaks) ? spec.peaks : []

  if (!spec || bands.length === 0) {
    return (
      <div className="structured-card physics-card">
        <div className="structured-card-header">
          <span className="structured-pill"><Atom size={13} /> Spectrum Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const width = 680
  const height = 200
  const barH = 40
  const padding = { top: 30, right: 20, bottom: 40, left: 50 }
  const chartW = width - padding.left - padding.right

  const maxWavelength = Math.max(...bands.map(b => b.end), ...peaks.map(p => p.wavelength), 1)
  const minWavelength = Math.min(...bands.map(b => b.start), ...peaks.map(p => p.wavelength), 0)
  const range = maxWavelength - minWavelength || 1

  const xPos = (val: number) => padding.left + ((val - minWavelength) / range) * chartW

  const maxIntensity = Math.max(...peaks.map(p => p.intensity), 1)

  return (
    <div className="structured-card physics-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Atom size={13} /> Spectrum</span>
        <h4>{spec.title || 'Spectral Analysis'}</h4>
      </div>
      <svg className="physics-svg" viewBox={`0 0 ${width} ${height}`}>
        <rect x={padding.left} y={padding.top} width={chartW} height={barH} rx="4" fill="#0e0c1a" />
        {bands.map((band, i) => (
          <rect
            key={i}
            x={xPos(band.start)}
            y={padding.top}
            width={Math.max(xPos(band.end) - xPos(band.start), 1)}
            height={barH}
            fill={band.color}
            opacity="0.85"
          />
        ))}
        {bands.map((band, i) => (
          <text key={`label-${i}`} x={(xPos(band.start) + xPos(band.end)) / 2} y={padding.top + barH + 16} textAnchor="middle" className="physics-axis-text" fontSize="9">
            {band.label}
          </text>
        ))}
        {peaks.map((peak, i) => {
          const x = xPos(peak.wavelength)
          const barHeight = (peak.intensity / maxIntensity) * 60
          return (
            <g key={`peak-${i}`}>
              <line x1={x} y1={padding.top + barH + 24} x2={x} y2={padding.top + barH + 24 - barHeight} stroke="#C58A57" strokeWidth="2" strokeLinecap="round" />
              <circle cx={x} cy={padding.top + barH + 24 - barHeight} r="3" fill="#C58A57" />
              {peak.label && (
                <text x={x} y={padding.top + barH + 24 - barHeight - 8} textAnchor="middle" className="physics-axis-text" fontSize="9" fill="#C58A57">
                  {peak.label}
                </text>
              )}
            </g>
          )
        })}
        {[0, 0.25, 0.5, 0.75, 1].map(step => {
          const val = minWavelength + range * step
          return (
            <text key={step} x={xPos(val)} y={height - 6} textAnchor="middle" className="physics-axis-text" fontSize="9">
              {val.toFixed(1)}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

function PhysicsOrbitalCard({ spec, raw }: { spec?: PhysicsOrbitalSpec; raw: string }) {
  const n = typeof spec?.n === 'number' ? spec.n : 2
  const l = typeof spec?.l === 'number' ? spec.l : 1
  const electronConfig = spec?.electronConfig || ''

  if (!spec) {
    return (
      <div className="structured-card physics-card">
        <div className="structured-card-header">
          <span className="structured-pill"><Atom size={13} /> Orbital Spec</span>
        </div>
        <pre><code>{raw}</code></pre>
      </div>
    )
  }

  const width = 400
  const height = 400
  const cx = width / 2
  const cy = height / 2

  const orbitalPaths: { d: string; color: string; label: string }[] = []

  const colors = ['#2F6F72', '#7A9E7E', '#4F7A9A', '#C58A57', '#7C6FA8']

  const shapes: Record<string, { d: string; label: string }[]> = {
    '0': [{ d: `M ${cx - 60},${cy} A 60,60 0 1,0 ${cx + 60},${cy} A 60,60 0 1,0 ${cx - 60},${cy}`, label: 's orbital' }],
    '1': [
      { d: `M ${cx},${cy - 80} C ${cx + 40},${cy - 40} ${cx + 40},${cy + 40} ${cx},${cy + 80} C ${cx - 40},${cy + 40} ${cx - 40},${cy - 40} ${cx},${cy - 80} Z`, label: 'pₓ orbital' },
    ],
    '2': [
      { d: `M ${cx - 50},${cy - 50} C ${cx - 20},${cy} ${cx + 20},${cy} ${cx + 50},${cy - 50} C ${cx + 20},${cy} ${cx + 20},${cy + 50} ${cx + 50},${cy + 50} C ${cx + 20},${cy} ${cx - 20},${cy} ${cx - 50},${cy + 50} C ${cx - 20},${cy} ${cx - 20},${cy - 50} ${cx - 50},${cy - 50} Z`, label: 'dₓᵧ orbital' },
    ],
  }

  const shapeKey = String(Math.min(l, 2))
  const shapeList = shapes[shapeKey] || shapes['0']

  shapeList.forEach((shape, i) => {
    orbitalPaths.push({ d: shape.d, color: colors[i % colors.length], label: shape.label })
  })

  const shells = Math.max(n, 2)
  const shellRings: { r: number; label: string }[] = []
  for (let s = 1; s <= shells; s++) {
    shellRings.push({ r: 40 + s * 50, label: `n=${s}` })
  }

  return (
    <div className="structured-card physics-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Atom size={13} /> Orbital</span>
        <h4>{spec.title || 'Atomic Orbital'}</h4>
      </div>
      <div className="orbital-layout">
        <svg className="orbital-svg" viewBox={`0 0 ${width} ${height}`}>
          {shellRings.map(shell => (
            <circle key={shell.r} cx={cx} cy={cy} r={shell.r} fill="none" stroke="#1a212d" strokeWidth="1" strokeDasharray="4 4" />
          ))}
          {orbitalPaths.map((orb, i) => (
            <path key={i} d={orb.d} fill={orb.color} fillOpacity="0.25" stroke={orb.color} strokeWidth="2" />
          ))}
          <circle cx={cx} cy={cy} r="6" fill="#C58A57" />
          {shellRings.map(shell => (
            <text key={shell.label} x={cx + shell.r + 8} y={cy + 4} className="physics-axis-text" fontSize="10" fill="#8995a7">
              {shell.label}
            </text>
          ))}
        </svg>
        <div className="orbital-info">
          <div className="orbital-quantum">
            <span className="orbital-q">n = {n}</span>
            <span className="orbital-q">l = {l}</span>
            {typeof spec?.m === 'number' && <span className="orbital-q">m = {spec.m}</span>}
          </div>
          <div className="orbital-label">{shapeList[0]?.label || 'orbital'}</div>
          {electronConfig && <div className="orbital-config"><code>{electronConfig}</code></div>}
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   STRUCTURED CONTENT RENDERER
   ═══════════════════════════════════════════════════════════════════ */

function StructuredContent({ content, onPrompt }: { content: string; onPrompt?: (text: string) => void }) {
  const segments = parseStructuredContent(content)
  return (
    <div className="structured-content">
      {segments.map((segment, index) => {
        if (segment.type === 'markdown') {
          return <Md key={`md-${index}`}>{segment.content}</Md>
        }
        if (segment.type === 'document' || segment.type === 'canvas') {
          return (
            <div key={`${segment.type}-${index}`} className={`structured-card ${segment.type}-card`}>
              <div className="structured-card-header">
                <span className="structured-pill">
                  <FileText size={13} />
                  {segment.type === 'document' ? 'Document' : 'Canvas'}
                </span>
                <h4>{segment.title}</h4>
              </div>
              <div className="structured-card-body">
                <Md>{segment.content}</Md>
              </div>
            </div>
          )
        }
        if (segment.type === 'chart') {
          return <ChartCard key={`chart-${index}`} chart={segment.chart} raw={segment.raw} />
        }
        if (segment.type === 'scorecard') {
          return <ScorecardBlock key={`scorecard-${index}`} scorecard={segment.scorecard} raw={segment.raw} />
        }
        if (segment.type === 'visual') {
          if (segment.visualType === 'chart') {
            return <ChartCard key={`visual-chart-${index}`} chart={normalizeVisualChart(segment.data as VisualChartSpec | undefined) || undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'donut') {
            return <DonutChartCard key={`visual-donut-${index}`} spec={segment.data as DonutSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'scoreboard') {
            return <VisualScoreboardCard key={`visual-scoreboard-${index}`} spec={segment.data as VisualScoreboardSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'table') {
            return <VisualTableCard key={`visual-table-${index}`} spec={segment.data as VisualTableSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'heatmap') {
            return <HeatmapCard key={`visual-heatmap-${index}`} spec={segment.data as HeatmapSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'timeline') {
            return <VisualTimelineCard key={`visual-timeline-${index}`} spec={segment.data as VisualTimelineSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'illustration') {
            return <IllustrationCard key={`visual-illustration-${index}`} spec={segment.data as IllustrationSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'math-equation') {
            return <MathEquationCard key={`visual-math-${index}`} spec={segment.data as MathEquationSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'physics-wave') {
            return <PhysicsWaveCard key={`visual-wave-${index}`} spec={segment.data as PhysicsWaveSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'physics-field') {
            return <PhysicsFieldCard key={`visual-field-${index}`} spec={segment.data as PhysicsFieldSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'physics-spectrum') {
            return <PhysicsSpectrumCard key={`visual-spectrum-${index}`} spec={segment.data as PhysicsSpectrumSpec | undefined} raw={segment.raw} />
          }
          if (segment.visualType === 'physics-orbital') {
            return <PhysicsOrbitalCard key={`visual-orbital-${index}`} spec={segment.data as PhysicsOrbitalSpec | undefined} raw={segment.raw} />
          }
          return (
            <div key={`visual-raw-${index}`} className="structured-card scorecard-block">
              <div className="structured-card-header">
                <span className="structured-pill"><BarChart3 size={13} /> {segment.visualType}</span>
              </div>
              <pre><code>{segment.raw}</code></pre>
            </div>
          )
        }
        if (segment.type === 'node-graph') {
          return <NodeGraphCard key={`node-graph-${index}`} graph={segment.graph} raw={segment.raw} onPrompt={onPrompt} />
        }
        if (segment.type === 'diagram') {
          return <FlowDiagram key={`diagram-${index}`} spec={segment.spec as DiagramSpec} raw={segment.raw} />
        }
        if (segment.type === 'd3graph') {
          return <D3Graph key={`d3graph-${index}`} spec={segment.spec as GraphSpec} raw={segment.raw} />
        }
        if (segment.type === 'widget') {
          return <EmbeddedWidget key={`widget-${segment.tag}-${index}`} tag={segment.tag} content={segment.content} />
        }
        if (segment.type === 'mermaid') {
          return <MermaidCard key={`mermaid-${index}`} content={segment.content} />
        }
        return null
      })}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   EVIDENCE RAIL — Colorful Source Cards
   ═══════════════════════════════════════════════════════════════════ */

function EvidenceRail({ evidence }: { evidence: EvidenceItem[] }) {
  return (
    <div className="evidence-rail">
      <div className="section-heading">
        <span className="section-kicker">Research Sources</span>
        <h4>{evidence.length} cited signals</h4>
      </div>
      <div className="evidence-grid">
        {evidence.map((item, index) => (
          <div key={`${item.url}-${index}`} className="evidence-card">
            <div className="evidence-card-top">
              <span className="source-chip">
                <Globe2 size={11} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                {item.source}
              </span>
              {typeof item.relu_score === 'number' && (
                <span className="source-score">
                  <TrendingUp size={11} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                  {item.relu_score.toFixed(2)}
                </span>
              )}
            </div>
            <div className="evidence-title">{item.title || item.claim.slice(0, 80)}</div>
            <p>{item.claim}</p>
            {item.url && (
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.url}
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   THINKING PANEL
   ═══════════════════════════════════════════════════════════════════ */

function ThinkingPanel({
  logs,
  plan,
  researchLevel,
  live,
}: {
  logs: ThinkingLogItem[]
  plan: string
  researchLevel: string
  live: boolean
}) {
  const visibleLogs = logs.slice(-2)
  return (
    <div className="thinking-panel">
      <div className="thinking-summary">
        <span className="structured-pill"><Activity size={13} /> Flow</span>
        <span>{logs.length} steps</span>
        <span className="thinking-level">{researchLevel}</span>
      </div>
      {plan.trim() && (
        <div className="thinking-plan">
          <div className="thinking-plan-title">Plan</div>
          <p>{plan.split('\n').map(line => line.trim()).filter(Boolean).slice(0, 2).join(' ')}</p>
        </div>
      )}
      <div className="thinking-log-list" aria-live={live ? 'polite' : undefined}>
        {visibleLogs.map((log, index) => (
          <div key={`${log.node}-${index}`} className="thinking-log-item">
            <strong>{log.title}</strong>
            <span>{log.detail}</span>
          </div>
        ))}
        {logs.length > visibleLogs.length && (
          <div className="thinking-log-more">
            Latest {visibleLogs.length} of {logs.length}
          </div>
        )}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN APPLICATION
   ═══════════════════════════════════════════════════════════════════ */

export default function App() {
  const [models, setModels] = useState<ModelEntry[]>([])
  const [selectedModel, setSelectedModel] = useState('groq/llama-3.3-70b-versatile')
  const [singleModelMode, setSingleModelMode] = useState(false)
  const [mode, setMode] = useState<'standard' | 'research' | 'reasoning'>('standard')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(310)
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('history')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [threads, setThreads] = useState<ThreadItem[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState(() => createSessionId())
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([])
  const [researchSessions, setResearchSessions] = useState<ResearchItem[]>([])
  const [artifactPanel, setArtifactPanel] = useState<{ title: string; content: string } | null>(null)
  const [artifactWidth, setArtifactWidth] = useState(460)
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])
  const [thinkingLog, setThinkingLog] = useState<ThinkingLogItem[]>([])
  const [statusText, setStatusText] = useState('')
  const [planPreview, setPlanPreview] = useState('')
  const [researchLevel, setResearchLevel] = useState('basic')
  const [temperature, setTemperature] = useState(0.1)
  const [uiError, setUiError] = useState('')
  const [apiKeys, setApiKeys] = useState({ groq: '', sarvam: '', openrouter: '' })
  const [firecrawlConfig, setFirecrawlConfig] = useState<FirecrawlSettings>(DEFAULT_FIRECRAWL)
  const [uiPrefs, setUiPrefs] = useState<UiSettings>(DEFAULT_UI)
  const [agentRuntime, setAgentRuntime] = useState<AgentRuntimeSettings>(DEFAULT_AGENT_RUNTIME)
  const [visualMode, setVisualMode] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const dataCursorRef = useRef(0)
  const resizeStateRef = useRef<null | { target: 'sidebar' | 'artifact'; startX: number; startWidth: number }>(null)

  const resetTransientState = useCallback(() => {
    setEvidence([])
    setThinkingLog([])
    setStatusText('')
    setPlanPreview('')
    setResearchLevel('basic')
    dataCursorRef.current = 0
  }, [])

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    setMessages,
    data,
    append,
  } = useChat({
    api: apiUrl('/api/chat'),
    body: { model: selectedModel, mode, temperature, visualsEnabled: visualMode, sessionId: currentSessionId },
    onFinish: () => {
      setStatusText('')
      setUiError('')
      refreshSidebar()
    },
    onError: (error: Error) => {
      setStatusText('')
      setUiError(error.message || 'The request failed. Verify the backend and provider settings.')
      console.error('Chat error:', error)
    },
  })

  const refreshSidebar = useCallback(() => {
    api.threads().then(result => setThreads(result.threads || [])).catch(() => {})
    api.artifacts().then(result => setArtifacts(result.artifacts || [])).catch(() => {})
    api.research().then(result => setResearchSessions(result.sessions || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!data || data.length === 0) return
    if (data.length < dataCursorRef.current) dataCursorRef.current = 0

    for (let index = dataCursorRef.current; index < data.length; index += 1) {
      const item = data[index] as Record<string, unknown>
      if (item.status) setStatusText(String(item.status))
      if (item.evidence) setEvidence(item.evidence as EvidenceItem[])
      if (item.thinking_log_append) {
        setThinkingLog(prev => [...prev, ...(item.thinking_log_append as ThinkingLogItem[])])
      }
      if (item.thinking_log) setThinkingLog(item.thinking_log as ThinkingLogItem[])
      if (item.plan) setPlanPreview(String(item.plan))
      if (item.research_level) setResearchLevel(String(item.research_level))
    }

    dataCursorRef.current = data.length
  }, [data])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, statusText, thinkingLog])

  useEffect(() => {
    const onMouseMove = (event: MouseEvent) => {
      const state = resizeStateRef.current
      if (!state) return
      if (state.target === 'sidebar') {
        setSidebarWidth(clamp(state.startWidth + (event.clientX - state.startX), 260, 420))
      } else {
        setArtifactWidth(clamp(state.startWidth - (event.clientX - state.startX), 360, 760))
      }
    }

    const onMouseUp = () => {
      if (!resizeStateRef.current) return
      resizeStateRef.current = null
      document.body.classList.remove('is-resizing')
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  useEffect(() => {
    api.models().then(result => {
      const normalized = normalizeModelsResponse(result)
      setModels(normalized.models)
      setSingleModelMode(normalized.singleModelMode)
      if (normalized.models.length > 0) setSelectedModel(current =>
        normalized.models.some(entry => entry.id === current) ? current : (normalized.defaultModel || normalized.models[0].id)
      )
      setUiError('')
    }).catch(() => {
      setUiError('Failed to load models from the backend. Verify the API server and provider settings.')
    })

    api.settings().then((settings: AppSettings) => {
      setTemperature(typeof settings.temperature === 'number' ? settings.temperature : 0.1)
      setApiKeys({
        groq: settings.apiKeys?.groq || '',
        sarvam: settings.apiKeys?.sarvam || '',
        openrouter: settings.apiKeys?.openrouter || '',
      })
      setFirecrawlConfig({
        ...DEFAULT_FIRECRAWL,
        ...(settings.firecrawl || {}),
      })
      setUiPrefs({
        ...DEFAULT_UI,
        ...(settings.ui || {}),
      })
      setAgentRuntime({
        ...DEFAULT_AGENT_RUNTIME,
        ...(settings.agentRuntime || {}),
      })
      setVisualMode(Boolean(settings.ui?.renderVisualsInline ?? DEFAULT_UI.renderVisualsInline))
    }).catch(() => {
      setUiError('Failed to load runtime settings. Verify the backend is running on port 8002.')
    })

    refreshSidebar()
  }, [refreshSidebar])

  const onNewChat = () => {
    setUiError('')
    setActiveThreadId(null)
    if (messages.length >= 2) {
      const title = messages.find((message: { role: string }) => message.role === 'user')?.content.slice(0, 60) || 'Chat'
      api.saveThread(
        currentSessionId,
        title,
        messages.map((message: { role: string; content: string }) => ({
          role: message.role,
          content: message.content,
        })),
      ).then(() => refreshSidebar()).catch(() => {})
    }
    setMessages([])
    setCurrentSessionId(createSessionId())
    resetTransientState()
  }

  const loadThread = async (id: string) => {
    try {
      const thread = await api.thread(id)
      setMessages(thread.messages?.map((message: { role: string; content: string }, index: number) => ({
        id: String(index),
        role: message.role as 'user' | 'assistant',
        content: message.content,
      })) || [])
      setActiveThreadId(id)
      setCurrentSessionId(id)
      resetTransientState()
      setUiError('')
    } catch (error) {
      setUiError(error instanceof Error ? error.message : 'Failed to load the selected thread.')
    }
  }

  const handleDeleteThread = async (event: ReactMouseEvent<HTMLButtonElement>, threadId: string) => {
    event.stopPropagation()
    if (deletingThreadId) return
    setDeletingThreadId(threadId)
    try {
      const response = await api.deleteThread(threadId)
      if (!response.ok) {
        throw new Error(`Failed with status ${response.status}`)
      }
      setThreads(current => current.filter(thread => thread.id !== threadId))
      if (activeThreadId === threadId) {
        setMessages([])
        setActiveThreadId(null)
        setCurrentSessionId(createSessionId())
        resetTransientState()
      }
      setUiError('')
    } catch (error) {
      setUiError(error instanceof Error ? error.message : 'Failed to delete the selected chat.')
    } finally {
      setDeletingThreadId(null)
    }
  }

  const openArtifact = async (id: string) => {
    try {
      const artifact = await api.artifact(id)
      setArtifactPanel({ title: artifact.title, content: artifact.content })
      setUiError('')
    } catch (error) {
      setUiError(error instanceof Error ? error.message : 'Failed to load the selected artifact.')
    }
  }

  const openResearch = async (id: string) => {
    try {
      const research = await api.researchItem(id)
      setArtifactPanel({ title: `Research: ${research.query?.slice(0, 40)}`, content: research.brief || '' })
      setUiError('')
    } catch (error) {
      setUiError(error instanceof Error ? error.message : 'Failed to load the selected research session.')
    }
  }

  const quickPrompt = useCallback((text: string) => {
    resetTransientState()
    setUiError('')
    setActiveThreadId(null)
    append({ role: 'user', content: text })
  }, [append, resetTransientState])

  const startResize = useCallback((target: 'sidebar' | 'artifact') => (event: ReactMouseEvent<HTMLButtonElement>) => {
    if (window.innerWidth <= 900) return
    resizeStateRef.current = {
      target,
      startX: event.clientX,
      startWidth: target === 'sidebar' ? sidebarWidth : artifactWidth,
    }
    document.body.classList.add('is-resizing')
    event.preventDefault()
  }, [artifactWidth, sidebarWidth])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const payload = event.data
      if (!payload || typeof payload !== 'object') return
      if (payload.type !== 'send-prompt' || typeof payload.text !== 'string') return
      const nextText = payload.text.trim()
      if (!nextText) return
      quickPrompt(nextText)
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [quickPrompt])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!input.trim() || isLoading) return
    resetTransientState()
    setUiError('')
    handleSubmit(event, {
      experimental_attachments: [],
    })
  }

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSubmit(event)
    }
  }

  const saveSettings = () => {
    api.saveSettings({
      temperature,
      apiKeys,
      firecrawl: firecrawlConfig,
      ui: uiPrefs,
      agentRuntime,
      search: { provider: 'duckduckgo', reranker: 'ReLU' },
    }).then(() => {
      return Promise.all([api.settings(), api.models()])
    }).then(([settings, modelsResponse]) => {
      const normalized = normalizeModelsResponse(modelsResponse)
      setModels(normalized.models)
      setSingleModelMode(normalized.singleModelMode)
      if (normalized.defaultModel) {
        setSelectedModel(current =>
          normalized.models.some(entry => entry.id === current) ? current : normalized.defaultModel || current
        )
      }
      setAgentRuntime({
        ...DEFAULT_AGENT_RUNTIME,
        ...(settings.agentRuntime || {}),
      })
      setUiError('')
      setSettingsOpen(false)
    }).catch((error) => {
      setUiError(error instanceof Error ? error.message : 'Failed to save runtime settings.')
      setSettingsOpen(false)
    })
  }

  const selectedModelEntry = models.find(model => model.id === selectedModel) || null
  const modelLabel = selectedModelEntry?.label || selectedModel
  const lastAssistantId = [...messages].reverse().find(message => message.role === 'assistant')?.id

  return (
    <div className="app-shell">
      <div className="app">
        {/* ── SIDEBAR ─────────────────────────────────────────────── */}
        <aside
          className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}
          style={sidebarOpen ? { width: sidebarWidth, minWidth: sidebarWidth } : undefined}
        >
          <div className="sidebar-header">
            <div className="logo-orb">R</div>
            <div>
              <h2>RAY Research</h2>
              <p>Autonomous AI Workstation</p>
            </div>
          </div>

          <div className="sidebar-tabs">
            {(['history', 'artifacts', 'research'] as SidebarTab[]).map(tab => (
              <button
                key={tab}
                className={`sidebar-tab ${sidebarTab === tab ? 'active' : ''}`}
                onClick={() => setSidebarTab(tab)}
              >
                {tab === 'history' && <><MessageSquare size={13} /> History</>}
                {tab === 'artifacts' && <><FileText size={13} /> Artifacts</>}
                {tab === 'research' && <><FlaskConical size={13} /> Research</>}
              </button>
            ))}
          </div>

          <div className="sidebar-content">
            {sidebarTab === 'history' && (
              threads.length === 0
                ? <div className="empty-state"><MessageSquare size={18} /><span>No conversations yet</span></div>
                : threads.map(thread => (
                  <div
                    key={thread.id}
                    className={`sidebar-item ${activeThreadId === thread.id ? 'active' : ''}`}
                    onClick={() => loadThread(thread.id)}
                  >
                    <div className="sidebar-item-body">
                      <span className="title">{thread.title}</span>
                      <span className="meta">{thread.message_count} msgs · {thread.updated_at?.slice(0, 10)}</span>
                    </div>
                    <button
                      type="button"
                      className="sidebar-item-delete"
                      aria-label={`Delete ${thread.title}`}
                      onClick={(event) => handleDeleteThread(event, thread.id)}
                      disabled={deletingThreadId === thread.id}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
            )}
            {sidebarTab === 'artifacts' && (
              artifacts.length === 0
                ? <div className="empty-state"><FileText size={18} /><span>No artifacts saved</span></div>
                : artifacts.map(artifact => (
                  <div key={artifact.id} className="sidebar-item" onClick={() => openArtifact(artifact.id)}>
                    <span className="title">📄 {artifact.title}</span>
                    <span className="meta">{artifact.type} · {artifact.created_at?.slice(0, 10)}</span>
                  </div>
                ))
            )}
            {sidebarTab === 'research' && (
              researchSessions.length === 0
                ? <div className="empty-state"><FlaskConical size={18} /><span>No research saved</span></div>
                : researchSessions.map(session => (
                  <div key={session.id} className="sidebar-item" onClick={() => openResearch(session.id)}>
                    <span className="title">🔬 {session.query?.slice(0, 50)}</span>
                    <span className="meta">{session.source_count} sources · {session.created_at?.slice(0, 10)}</span>
                  </div>
                ))
            )}
          </div>

          <div className="sidebar-actions">
            <button className="new-chat-btn" onClick={onNewChat}>
              <Plus size={15} /> New Chat
            </button>
          </div>
        </aside>
        {sidebarOpen && (
          <button
            type="button"
            className="panel-resize-handle left"
            aria-label="Resize sidebar"
            onMouseDown={startResize('sidebar')}
          />
        )}

        {/* ── MAIN CONTENT AREA ───────────────────────────────────── */}
        <div className="main">
          <div className="topbar">
            <button className="toggle-sidebar-btn" onClick={() => setSidebarOpen(open => !open)}>
              {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
            </button>
            <div className="topbar-control">
              <span className="topbar-label">Model</span>
              {singleModelMode ? (
                <div className="topbar-single-model">
                  <Brain size={14} />
                  <span>{modelLabel}</span>
                </div>
              ) : (
                <select className="topbar-select" value={selectedModel} onChange={event => setSelectedModel(event.target.value)}>
                  {models.map(model => <option key={model.id} value={model.id}>{model.label}</option>)}
                </select>
              )}
            </div>
            <div className="topbar-control">
              <span className="topbar-label">Mode</span>
              <select className="topbar-select" value={mode} onChange={event => setMode(event.target.value as typeof mode)}>
                <option value="standard">⚡ Standard</option>
                <option value="research">🔬 Research</option>
                <option value="reasoning">🧠 Reasoning</option>
              </select>
            </div>
            <div className="topbar-spacer" />
            <button className="settings-btn" onClick={() => setSettingsOpen(true)}>
              <Settings size={14} /> Settings
            </button>
          </div>

          {selectedModelEntry && (
            <div className="model-spotlight">
              <div className="model-spotlight-copy">
                <strong>{selectedModelEntry.label}</strong>
                <span>{selectedModelEntry.specialty}</span>
                <span>{visualMode ? 'Visual responses enabled' : 'Text-first responses'}</span>
              </div>
              <div className="model-spotlight-meta">
                <span className="model-meta-pill"><Brain size={12} /> {selectedModelEntry.provider}</span>
                {selectedModelEntry.features.slice(0, 2).map(feature => (
                  <span key={feature} className="model-feature-pill">{feature}</span>
                ))}
              </div>
            </div>
          )}

          {uiError && (
            <div className="error-banner" role="alert">
              <Shield size={14} />
              <span>{uiError}</span>
            </div>
          )}

          {/* ── Messages Stream ───────────────────────────────────── */}
          <div className="messages">
            <div className="messages-inner">
              {messages.length === 0 && !isLoading && (
                <div className="welcome">
                  <div className="welcome-badge">Minimal chat workspace</div>
                  <h1>RAY</h1>
                  <p>
                    Ask a question, keep the response text-first by default, and enable visuals only for answers that benefit from charts, diagrams, or formatted briefs.
                  </p>
                  <div className="welcome-cards">
                    <div className="welcome-card" onClick={() => quickPrompt('Compare top reasoning models in plain markdown')}>
                      <div className="wc-title"><MessageSquare size={14} /> Plain answer</div>
                      <div className="wc-desc">Default text-first response</div>
                    </div>
                    <div className="welcome-card" onClick={() => { setVisualMode(true); quickPrompt('Compare top reasoning models and include a leaderboard chart') }}>
                      <div className="wc-title"><BarChart3 size={14} /> Visual answer</div>
                      <div className="wc-desc">Turn visuals on for charts and diagrams</div>
                    </div>
                    <div className="welcome-card" onClick={() => quickPrompt('Research self-hosted Firecrawl vs cloud and summarize the trade-offs')}>
                      <div className="wc-title"><FlaskConical size={14} /> Research</div>
                      <div className="wc-desc">Web-assisted answer when needed</div>
                    </div>
                  </div>
                </div>
              )}

              {messages.map(message => (
                <div key={message.id} className={`message ${message.role === 'assistant' ? 'msg-appear' : ''}`}>
                  <div className="message-header">
                    <div className={`message-avatar ${message.role}`}>
                      {message.role === 'user' ? 'U' : 'R'}
                    </div>
                    <span className="message-role">{message.role === 'user' ? 'You' : 'RAY · ' + modelLabel}</span>
                  </div>
                  <div className={`message-body ${message.role === 'user' ? 'user-body' : 'assistant-body'}`}>
                    <StructuredContent content={message.content} onPrompt={quickPrompt} />

                    {message.role === 'assistant' && message.id === lastAssistantId && (evidence.length > 0 || thinkingLog.length > 0) && (
                      <ResponseMetaRow
                        evidence={evidence}
                        thinkingLog={thinkingLog}
                        mode={mode}
                      />
                    )}

                    {message.role === 'assistant' && message.id === lastAssistantId && uiPrefs.showThinkingLogs && thinkingLog.length > 0 && (
                      <ThinkingPanel
                        logs={thinkingLog}
                        plan={planPreview}
                        researchLevel={researchLevel}
                        live={isLoading}
                      />
                    )}

                    {message.role === 'assistant' && message.id === lastAssistantId && evidence.length > 0 && (
                      <EvidenceRail evidence={evidence} />
                    )}
                  </div>
                </div>
              ))}

              {/* ── Loading / Thinking State ───────────────────────── */}
              {isLoading && (
                <div className="message msg-appear">
                  <div className="message-header">
                    <div className="message-avatar assistant">R</div>
                    <span className="message-role">RAY · {modelLabel}</span>
                  </div>
                  {!messages.length || messages[messages.length - 1]?.role === 'user' ? (
                    <div className="thinking-block">
                      <div className="thinking-visual">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div className="chakra-spinner" />
                          <div className="thinking-status">{statusText || `Analyzing with ${modelLabel}…`}</div>
                        </div>
                      </div>
                      {uiPrefs.showThinkingLogs && thinkingLog.length > 0 && (
                        <div className="thinking-inline-log">
                          <strong>{thinkingLog[thinkingLog.length - 1]?.title}</strong>
                          <span>{thinkingLog[thinkingLog.length - 1]?.detail}</span>
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* ── Input Area ─────────────────────────────────────────── */}
          <div className="input-area">
            <div className="input-area-inner">
              <form onSubmit={onSubmit}>
                <div className="input-box">
                  <div className="input-box-main">
                    <div className="composer-toolbar">
                      <button
                        type="button"
                        className={`composer-toggle ${visualMode ? 'active' : ''}`}
                        onClick={() => setVisualMode(current => !current)}
                      >
                        <BarChart3 size={14} />
                        {visualMode ? 'Visuals when useful' : 'Text first'}
                      </button>
                      <span className="composer-toolbar-note">
                        {visualMode ? 'Use visuals only when they clarify the answer.' : 'Keep replies plain unless visuals are necessary.'}
                      </span>
                    </div>
                    <textarea
                      value={input}
                      onChange={handleInputChange}
                      onKeyDown={handleKeyDown}
                      placeholder={`Ask anything… (${mode} mode)`}
                      rows={1}
                      disabled={isLoading}
                    />
                  </div>
                  <div className="input-box-actions">
                    <div className="input-box-meta">
                      <span>{mode}</span>
                      <span>{visualMode ? 'adaptive visuals' : 'plain output'}</span>
                    </div>
                    {isLoading ? (
                      <button type="button" className="stop-btn" onClick={stop}>
                        <Square size={12} /> Stop
                      </button>
                    ) : (
                      <button type="submit" className="send-btn" disabled={!input.trim()} aria-label="Send message">
                        <Send size={16} />
                      </button>
                    )}
                  </div>
                </div>
              </form>
              <div className="input-hint">
                {modelLabel} · {mode} · {visualMode ? 'visuals only when needed' : 'plain text by default'}
              </div>
            </div>
          </div>
        </div>

        {/* ── Artifact Side Panel ──────────────────────────────────── */}
        {artifactPanel && (
          <>
            <button
              type="button"
              className="panel-resize-handle right"
              aria-label="Resize details panel"
              onMouseDown={startResize('artifact')}
            />
            <div className="artifact-panel" style={{ width: artifactWidth, minWidth: Math.min(artifactWidth, 380) }}>
            <div className="artifact-panel-header">
              <h3>{artifactPanel.title}</h3>
              <button className="modal-close" onClick={() => setArtifactPanel(null)}><X size={18} /></button>
            </div>
            <div className="artifact-panel-body">
              <StructuredContent content={artifactPanel.content} onPrompt={quickPrompt} />
            </div>
            </div>
          </>
        )}

        {/* ── Settings Modal ──────────────────────────────────────── */}
        {settingsOpen && (
          <div className="modal-overlay" onClick={() => setSettingsOpen(false)}>
            <div className="modal" onClick={event => event.stopPropagation()}>
              <div className="modal-header">
                <h3>⚙️ Runtime Settings</h3>
                <button className="modal-close" onClick={() => setSettingsOpen(false)}><X size={18} /></button>
              </div>
              <div className="modal-body">
                <div className="settings-grid">
                  <div className="form-group">
                    <label className="form-label">Temperature <span className="form-range-val">{temperature.toFixed(2)}</span></label>
                    <input
                      type="range"
                      className="form-range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={temperature}
                      onChange={event => setTemperature(parseFloat(event.target.value))}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Groq API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      value={apiKeys.groq}
                      onChange={event => setApiKeys(current => ({ ...current, groq: event.target.value }))}
                      placeholder="gsk_..."
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Sarvam API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      value={apiKeys.sarvam}
                      onChange={event => setApiKeys(current => ({ ...current, sarvam: event.target.value }))}
                      placeholder="sk_..."
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">OpenRouter API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      value={apiKeys.openrouter}
                      onChange={event => setApiKeys(current => ({ ...current, openrouter: event.target.value }))}
                      placeholder="sk-or-..."
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Agent Runtime</label>
                    <select
                      className="form-select"
                      value={agentRuntime.backend}
                      onChange={event => setAgentRuntime(current => ({ ...current, backend: event.target.value }))}
                    >
                      <option value="langgraph">Built-in LangGraph backend</option>
                      <option value="codex_cli">Codex CLI via Groq</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Codex CLI Path</label>
                    <input
                      type="text"
                      className="form-input"
                      value={agentRuntime.codexPath}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexPath: event.target.value }))}
                      placeholder="codex"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Codex Model</label>
                    <input
                      type="text"
                      className="form-input"
                      value={agentRuntime.codexModel}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexModel: event.target.value }))}
                      placeholder="openai/gpt-oss-20b"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Codex Provider ID</label>
                    <input
                      type="text"
                      className="form-input"
                      value={agentRuntime.codexProviderId}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexProviderId: event.target.value }))}
                      placeholder="groq"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Groq OpenAI Base URL</label>
                    <input
                      type="text"
                      className="form-input"
                      value={agentRuntime.codexBaseUrl}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexBaseUrl: event.target.value }))}
                      placeholder="https://api.groq.com/openai/v1"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Codex Sandbox</label>
                    <select
                      className="form-select"
                      value={agentRuntime.codexSandbox}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexSandbox: event.target.value }))}
                    >
                      <option value="read-only">read-only</option>
                      <option value="workspace-write">workspace-write</option>
                      <option value="danger-full-access">danger-full-access</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Codex Approval Policy</label>
                    <select
                      className="form-select"
                      value={agentRuntime.codexApprovalPolicy}
                      onChange={event => setAgentRuntime(current => ({ ...current, codexApprovalPolicy: event.target.value }))}
                    >
                      <option value="never">never</option>
                      <option value="on-request">on-request</option>
                      <option value="untrusted">untrusted</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Visual Rendering by Default</label>
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={uiPrefs.renderVisualsInline}
                        onChange={event => {
                          const checked = event.target.checked
                          setUiPrefs(current => ({ ...current, renderVisualsInline: checked }))
                          setVisualMode(checked)
                        }}
                      />
                      <span>Start chats with visual responses enabled</span>
                    </label>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Firecrawl Strategy</label>
                    <select
                      className="form-select"
                      value={firecrawlConfig.strategy}
                      onChange={event => setFirecrawlConfig(current => ({ ...current, strategy: event.target.value }))}
                    >
                      <option value="self_hosted_first">Self-hosted first (recommended)</option>
                      <option value="cloud_only">Cloud only</option>
                      <option value="self_hosted_only">Self-hosted only</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Firecrawl Self-host URL</label>
                    <input
                      type="text"
                      className="form-input"
                      value={firecrawlConfig.baseUrl}
                      onChange={event => setFirecrawlConfig(current => ({ ...current, baseUrl: event.target.value }))}
                      placeholder="http://localhost:3002"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Firecrawl Cloud URL</label>
                    <input
                      type="text"
                      className="form-input"
                      value={firecrawlConfig.cloudUrl}
                      onChange={event => setFirecrawlConfig(current => ({ ...current, cloudUrl: event.target.value }))}
                      placeholder="https://api.firecrawl.dev"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Firecrawl Fallback API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      value={firecrawlConfig.fallbackApiKey}
                      onChange={event => setFirecrawlConfig(current => ({ ...current, fallbackApiKey: event.target.value }))}
                      placeholder="fc-..."
                    />
                  </div>
                </div>

                <div className="settings-note">
                  <div className="section-kicker">Model Access</div>
                  <p>
                    The app works with a single configured model, and it automatically exposes model selection when
                    more providers are available. Add one API key to start, or add multiple providers to unlock
                    a richer model picker with specialties for chat, reasoning, coding, and research.
                  </p>
                </div>

                <div className="settings-note" style={{ marginTop: 12 }}>
                  <div className="section-kicker">Codex via Groq</div>
                  <p>
                    Switch the runtime to <code>Codex CLI via Groq</code> when you want the chat UI to act as a visual shell
                    around the local Codex agent. The Groq API key is reused, and Codex is configured against the
                    OpenAI-compatible Groq endpoint at <code>https://api.groq.com/openai/v1</code>.
                  </p>
                </div>

                <div className="settings-note" style={{ marginTop: 12 }}>
                  <div className="section-kicker">Visual Mode</div>
                  <p>
                    Keep visual mode off for a simpler chat experience. Turn it on only when you want charts,
                    diagrams, or structured document-style output inside the conversation.
                  </p>
                </div>

                <div className="settings-note" style={{ marginTop: 12 }}>
                  <div className="section-kicker">Firecrawl Self-Host Setup</div>
                  <p>
                    Run <code>scripts/start_firecrawl_selfhost.sh</code> to clone and start Firecrawl locally via Docker Compose.
                    The default endpoint is <code>http://localhost:3002</code>. No API key is required for self-hosted instances
                    when <code>USE_DB_AUTHENTICATION=false</code>.
                  </p>
                </div>

                <div className="settings-note" style={{ marginTop: 12 }}>
                  <div className="section-kicker">Research Pipeline</div>
                  <p>
                    DuckDuckGo handles fast basic search, Firecrawl handles deep page crawling,
                    ReLU reranking filters evidence by semantic relevance, and the frontend renders
                    charts, documents, diagrams, and thinking logs inline — all powered by Vercel AI SDK streaming.
                  </p>
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn-ghost" onClick={() => setSettingsOpen(false)}>Cancel</button>
                <button className="btn-primary" onClick={saveSettings}>
                  <Shield size={14} /> Save Settings
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
