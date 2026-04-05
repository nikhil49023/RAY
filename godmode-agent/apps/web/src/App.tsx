import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from 'react'
import { useChat } from '@ai-sdk/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Activity, Brain, ChartColumn, FileText, FlaskConical, MessageSquare,
  PanelLeft, PanelLeftClose, Plus, Send, Settings, Square,
  Workflow, X, Zap, TrendingUp, BarChart3, Shield, Globe2,
} from 'lucide-react'

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

type SidebarTab = 'history' | 'artifacts' | 'research'
type RenderSegment =
  | { type: 'markdown'; content: string }
  | { type: 'document' | 'canvas'; title: string; content: string }
  | { type: 'chart'; raw: string; chart?: ChartSpec }
  | { type: 'scorecard'; raw: string; scorecard?: ScorecardSpec }
  | { type: 'mermaid'; content: string }

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  if (!response.ok) {
    const detail = (await response.text().catch(() => '')).trim()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
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
  models: () => requestJson<ModelsResponse>('/api/models'),
  threads: () => requestJson<{ threads?: ThreadItem[] }>('/api/threads'),
  thread: (id: string) => requestJson<{ messages?: { role: string; content: string }[] }>(`/api/threads/${id}`),
  saveThread: (title: string, messages: { role: string; content: string }[]) =>
    requestJson<{ id: string }>('/api/threads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, messages }),
    }),
  deleteThread: (id: string) => fetch(`/api/threads/${id}`, { method: 'DELETE' }),
  artifacts: () => requestJson<{ artifacts?: ArtifactItem[] }>('/api/artifacts'),
  artifact: (id: string) => requestJson<{ title: string; content: string }>(`/api/artifacts/${id}`),
  research: () => requestJson<{ sessions?: ResearchItem[] }>('/api/research'),
  researchItem: (id: string) => requestJson<{ query?: string; brief?: string }>(`/api/research/${id}`),
  settings: () => requestJson<AppSettings>('/api/settings'),
  saveSettings: (settings: object) =>
    requestJson('/api/settings', {
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

/* ── Indian-Authentic Vibrant Chart Palette ────────────────────── */
const CHART_COLORS = [
  '#00BFA6', // chakra teal
  '#FF6B35', // saffron
  '#FFD700', // gold
  '#E91E63', // lotus pink
  '#38BDF8', // sky blue
  '#A78BFA', // lavender
  '#F97316', // deep orange
  '#2DD4BF', // mint
]

/* ═══════════════════════════════════════════════════════════════════
   MARKDOWN RENDERER
   ═══════════════════════════════════════════════════════════════════ */

function Md({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
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

function parseStructuredContent(content: string): RenderSegment[] {
  if (!content) return []

  const pattern = /<(document|canvas):\s*(.*?)>([\s\S]*?)<\/(?:document|canvas)>|```(chart|scorecard|mermaid)\s*([\s\S]*?)```/gi
  const segments: RenderSegment[] = []
  let lastIndex = 0

  for (const match of content.matchAll(pattern)) {
    const start = match.index ?? 0
    if (start > lastIndex) {
      const markdown = content.slice(lastIndex, start)
      if (markdown.trim()) segments.push({ type: 'markdown', content: markdown.trim() })
    }

    const blockType = match[1]?.toLowerCase()
    const title = match[2]?.trim()
    const body = match[3]?.trim()
    const fenceType = match[4]?.toLowerCase()
    const fenceBody = match[5]?.trim() || ''

    if (blockType === 'document' || blockType === 'canvas') {
      segments.push({
        type: blockType,
        title: title || (blockType === 'document' ? 'Document' : 'Canvas'),
        content: body || '',
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
    }

    lastIndex = start + match[0].length
  }

  if (lastIndex < content.length) {
    const markdown = content.slice(lastIndex)
    if (markdown.trim()) segments.push({ type: 'markdown', content: markdown.trim() })
  }

  return segments.length > 0 ? segments : [{ type: 'markdown', content }]
}

/* ═══════════════════════════════════════════════════════════════════
   MERMAID CARD
   ═══════════════════════════════════════════════════════════════════ */

function MermaidCard({ content }: { content: string }) {
  const labels = Array.from(content.matchAll(/\[(.*?)\]|\((.*?)\)|\{(.*?)\}/g))
    .map(match => match[1] || match[2] || match[3] || '')
    .filter(Boolean)
    .slice(0, 8)

  return (
    <div className="structured-card mermaid-card">
      <div className="structured-card-header">
        <span className="structured-pill"><Workflow size={13} /> Diagram</span>
      </div>
      {labels.length > 0 && (
        <div className="mermaid-preview">
          {labels.map((label, index) => (
            <div key={`${label}-${index}`} className="mermaid-node-row">
              <div className="mermaid-node">{label}</div>
              {index < labels.length - 1 && <span className="mermaid-arrow">→</span>}
            </div>
          ))}
        </div>
      )}
      <pre className="mermaid-code"><code>{content}</code></pre>
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

        {normalized.type === 'line'
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
                  style={{ filter: `drop-shadow(0 2px 4px ${color}40)` }}
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
                      style={{ filter: `drop-shadow(0 4px 8px ${item.color || CHART_COLORS[seriesIndex % CHART_COLORS.length]}30)` }}
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

/* ═══════════════════════════════════════════════════════════════════
   STRUCTURED CONTENT RENDERER
   ═══════════════════════════════════════════════════════════════════ */

function StructuredContent({ content }: { content: string }) {
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
        return <MermaidCard key={`mermaid-${index}`} content={segment.content} />
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
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('history')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [threads, setThreads] = useState<ThreadItem[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([])
  const [researchSessions, setResearchSessions] = useState<ResearchItem[]>([])
  const [artifactPanel, setArtifactPanel] = useState<{ title: string; content: string } | null>(null)
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
    api: '/api/chat',
    body: { model: selectedModel, mode, temperature, visualsEnabled: visualMode },
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
    if (messages.length >= 2) {
      const title = messages.find((message: { role: string }) => message.role === 'user')?.content.slice(0, 60) || 'Chat'
      api.saveThread(
        title,
        messages.map((message: { role: string; content: string }) => ({
          role: message.role,
          content: message.content,
        })),
      ).then(() => refreshSidebar()).catch(() => {})
    }
    setMessages([])
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
      resetTransientState()
      setUiError('')
    } catch (error) {
      setUiError(error instanceof Error ? error.message : 'Failed to load the selected thread.')
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

  const quickPrompt = (text: string) => {
    resetTransientState()
    setUiError('')
    append({ role: 'user', content: text })
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!input.trim() || isLoading) return
    resetTransientState()
    setUiError('')
    handleSubmit(event)
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
        <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
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
                  <div key={thread.id} className="sidebar-item" onClick={() => loadThread(thread.id)}>
                    <span className="title">{thread.title}</span>
                    <span className="meta">{thread.message_count} msgs · {thread.updated_at?.slice(0, 10)}</span>
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
                    <StructuredContent content={message.content} />

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
              <div className="composer-toolbar">
                <button
                  type="button"
                  className={`composer-toggle ${visualMode ? 'active' : ''}`}
                  onClick={() => setVisualMode(current => !current)}
                >
                  <BarChart3 size={14} />
                  {visualMode ? 'Visuals On' : 'Visuals Off'}
                </button>
                <span className="composer-toolbar-note">
                  {visualMode
                    ? 'Visual blocks appear only when the response actually benefits from them.'
                    : 'Responses stay in plain markdown unless you explicitly enable visuals.'}
                </span>
              </div>
              <form onSubmit={onSubmit}>
                <div className="input-box">
                  <textarea
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder={`Ask anything… (${mode} mode)`}
                    rows={1}
                    disabled={isLoading}
                  />
                  {isLoading ? (
                    <button type="button" className="stop-btn" onClick={stop}>
                      <Square size={12} /> Stop
                    </button>
                  ) : (
                    <button type="submit" className="send-btn" disabled={!input.trim()}>
                      <Send size={16} />
                    </button>
                  )}
                </div>
              </form>
              <div className="input-hint">
                {modelLabel} · {mode} mode · {visualMode ? 'visuals available on demand' : 'plain text output'}
              </div>
            </div>
          </div>
        </div>

        {/* ── Artifact Side Panel ──────────────────────────────────── */}
        {artifactPanel && (
          <div className="artifact-panel">
            <div className="artifact-panel-header">
              <h3>{artifactPanel.title}</h3>
              <button className="modal-close" onClick={() => setArtifactPanel(null)}><X size={18} /></button>
            </div>
            <div className="artifact-panel-body">
              <StructuredContent content={artifactPanel.content} />
            </div>
          </div>
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
