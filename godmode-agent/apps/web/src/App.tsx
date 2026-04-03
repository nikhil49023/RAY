import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from 'react'
import { useChat } from '@ai-sdk/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Activity, Brain, ChartColumn, Compass, FileText, FlaskConical, MessageSquare,
  PanelLeft, PanelLeftClose, Plus, Search, Send, Settings, Sparkles, Square,
  Workflow, X, Zap,
} from 'lucide-react'

interface ModelEntry { id: string; label: string }
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
interface AppSettings {
  temperature?: number
  apiKeys?: { groq?: string; sarvam?: string; openrouter?: string }
  firecrawl?: Partial<FirecrawlSettings>
  ui?: Partial<UiSettings>
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

type SidebarTab = 'history' | 'artifacts' | 'research'
type RenderSegment =
  | { type: 'markdown'; content: string }
  | { type: 'document' | 'canvas'; title: string; content: string }
  | { type: 'chart'; raw: string; chart?: ChartSpec }
  | { type: 'mermaid'; content: string }

const api = {
  models: () => fetch('/api/models').then(r => r.json()),
  threads: () => fetch('/api/threads').then(r => r.json()),
  thread: (id: string) => fetch(`/api/threads/${id}`).then(r => r.json()),
  saveThread: (title: string, messages: { role: string; content: string }[]) =>
    fetch('/api/threads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, messages }),
    }).then(r => r.json()),
  deleteThread: (id: string) => fetch(`/api/threads/${id}`, { method: 'DELETE' }),
  artifacts: () => fetch('/api/artifacts').then(r => r.json()),
  artifact: (id: string) => fetch(`/api/artifacts/${id}`).then(r => r.json()),
  research: () => fetch('/api/research').then(r => r.json()),
  researchItem: (id: string) => fetch(`/api/research/${id}`).then(r => r.json()),
  settings: () => fetch('/api/settings').then(r => r.json()),
  saveSettings: (settings: object) =>
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }).then(r => r.json()),
}

const DEFAULT_FIRECRAWL: FirecrawlSettings = {
  strategy: 'self_hosted_first',
  baseUrl: 'http://localhost:3002',
  cloudUrl: 'https://api.firecrawl.dev',
  fallbackApiKey: '',
}

const DEFAULT_UI: UiSettings = {
  showThinkingLogs: true,
  renderVisualsInline: true,
  researchOutput: 'document',
}

const CHART_COLORS = ['#2dd4bf', '#f97316', '#38bdf8', '#facc15', '#fb7185']

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

  const pattern = /<(document|canvas):\s*(.*?)>([\s\S]*?)<\/(?:document|canvas)>|```(chart|mermaid)\s*([\s\S]*?)```/gi
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
    } else if (fenceType === 'chart') {
      let chart: ChartSpec | undefined
      try {
        chart = JSON.parse(fenceBody) as ChartSpec
      } catch {
        chart = undefined
      }
      segments.push({ type: 'chart', raw: fenceBody, chart })
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

function MermaidCard({ content }: { content: string }) {
  const labels = Array.from(content.matchAll(/\[(.*?)\]|\((.*?)\)|\{(.*?)\}/g))
    .map(match => match[1] || match[2] || match[3] || '')
    .filter(Boolean)
    .slice(0, 6)

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
  const width = 640
  const height = 280
  const padding = { top: 24, right: 16, bottom: 46, left: 44 }
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
        <span className="structured-pill"><ChartColumn size={13} /> Visual Render</span>
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
        {[0, 0.25, 0.5, 0.75, 1].map(step => {
          const y = padding.top + chartHeight - (chartHeight * step)
          const value = Math.round(maxValue * step)
          return (
            <g key={step}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="chart-grid-line" />
              <text x={padding.left - 10} y={y + 4} className="chart-axis-text">{value}</text>
            </g>
          )
        })}

        {normalized.type === 'line'
          ? series.map((item, index) => (
            <g key={item.label}>
              <polyline
                fill="none"
                stroke={item.color || CHART_COLORS[index % CHART_COLORS.length]}
                strokeWidth="3"
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
                    fill={item.color || CHART_COLORS[index % CHART_COLORS.length]}
                  />
                )
              })}
            </g>
          ))
          : labels.map((label, labelIndex) => {
            const groupWidth = chartWidth / Math.max(labels.length, 1)
            const innerWidth = groupWidth * 0.78
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
                      width={Math.max(barWidth - 6, 10)}
                      height={barHeight}
                      rx="8"
                      fill={item.color || CHART_COLORS[seriesIndex % CHART_COLORS.length]}
                    />
                  )
                })}
              </g>
            )
          })}

        {labels.map((label, index) => {
          const x = padding.left + ((index + 0.5) * (chartWidth / Math.max(labels.length, 1)))
          return (
            <text key={label} x={x} y={height - 16} textAnchor="middle" className="chart-axis-text chart-axis-label">
              {label}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

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
        return <MermaidCard key={`mermaid-${index}`} content={segment.content} />
      })}
    </div>
  )
}

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
              <span className="source-chip">{item.source}</span>
              {typeof item.relu_score === 'number' && (
                <span className="source-score">ReLU {item.relu_score.toFixed(2)}</span>
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
  return (
    <details className="thinking-panel" open={live || logs.length <= 3}>
      <summary>
        <div className="thinking-summary">
          <span className="structured-pill"><Activity size={13} /> Thinking Log</span>
          <span>{logs.length} orchestration events</span>
          <span className="thinking-level">{researchLevel} research</span>
        </div>
      </summary>
      {plan.trim() && (
        <div className="thinking-plan">
          <div className="thinking-plan-title">Plan snapshot</div>
          <Md>{plan}</Md>
        </div>
      )}
      <div className="thinking-log-list">
        {logs.map((log, index) => (
          <div key={`${log.node}-${index}`} className="thinking-log-item">
            <div className="thinking-log-head">
              <strong>{log.title}</strong>
              <span>{log.node}</span>
            </div>
            <p>{log.detail}</p>
            <div className="thinking-log-meta">
              {log.provider && <span>{log.provider}</span>}
              {log.reranker && <span>{log.reranker}</span>}
              {typeof log.result_count === 'number' && <span>{log.result_count} results</span>}
              {log.model && <span>{log.model}</span>}
            </div>
          </div>
        ))}
      </div>
    </details>
  )
}

export default function App() {
  const [models, setModels] = useState<ModelEntry[]>([])
  const [selectedModel, setSelectedModel] = useState('groq/llama-3.3-70b-versatile')
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
  const [apiKeys, setApiKeys] = useState({ groq: '', sarvam: '', openrouter: '' })
  const [firecrawlConfig, setFirecrawlConfig] = useState<FirecrawlSettings>(DEFAULT_FIRECRAWL)
  const [uiPrefs, setUiPrefs] = useState<UiSettings>(DEFAULT_UI)
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
    body: { model: selectedModel, mode, temperature },
    onFinish: () => {
      setStatusText('')
      refreshSidebar()
    },
    onError: (error: Error) => {
      setStatusText('')
      console.error('Chat error:', error)
    },
  })

  const refreshSidebar = useCallback(() => {
    api.threads().then((result: { threads?: ThreadItem[] }) => setThreads(result.threads || [])).catch(() => {})
    api.artifacts().then((result: { artifacts?: ArtifactItem[] }) => setArtifacts(result.artifacts || [])).catch(() => {})
    api.research().then((result: { sessions?: ResearchItem[] }) => setResearchSessions(result.sessions || [])).catch(() => {})
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
    api.models().then((result: { models?: Record<string, string> }) => {
      const entries = Object.entries(result.models || {}).map(([id, label]) => ({ id, label }))
      setModels(entries)
      if (entries.length > 0) setSelectedModel(current =>
        entries.some(entry => entry.id === current) ? current : entries[0].id
      )
    }).catch(() => {})

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
    }).catch(() => {})

    refreshSidebar()
  }, [refreshSidebar])

  const onNewChat = () => {
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
    } catch {
      // ignore
    }
  }

  const openArtifact = async (id: string) => {
    try {
      const artifact = await api.artifact(id)
      setArtifactPanel({ title: artifact.title, content: artifact.content })
    } catch {
      // ignore
    }
  }

  const openResearch = async (id: string) => {
    try {
      const research = await api.researchItem(id)
      setArtifactPanel({ title: `Research: ${research.query?.slice(0, 40)}`, content: research.brief || '' })
    } catch {
      // ignore
    }
  }

  const quickPrompt = (text: string) => {
    resetTransientState()
    append({ role: 'user', content: text })
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!input.trim() || isLoading) return
    resetTransientState()
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
      search: { provider: 'duckduckgo', reranker: 'ReLU' },
    }).then(() => setSettingsOpen(false)).catch(() => setSettingsOpen(false))
  }

  const modelLabel = models.find(model => model.id === selectedModel)?.label || selectedModel
  const lastAssistantId = [...messages].reverse().find(message => message.role === 'assistant')?.id

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <div className="app">
        <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
          <div className="sidebar-header">
            <div className="logo-orb">R</div>
            <div>
              <h2>RAY Research</h2>
              <p>Glass-box AI workstation</p>
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

        <div className="main">
          <div className="topbar">
            <button className="toggle-sidebar-btn" onClick={() => setSidebarOpen(open => !open)}>
              {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
            </button>
            <span className="topbar-label">Model</span>
            <select className="topbar-select" value={selectedModel} onChange={event => setSelectedModel(event.target.value)}>
              {models.map(model => <option key={model.id} value={model.id}>{model.label}</option>)}
            </select>
            <span className="topbar-label">Mode</span>
            <select className="topbar-select" value={mode} onChange={event => setMode(event.target.value as typeof mode)}>
              <option value="standard">⚡ Standard</option>
              <option value="research">🔬 Research</option>
              <option value="reasoning">🧠 Reasoning</option>
            </select>
            <div className="topbar-pills">
              <span className="signal-pill"><Search size={13} /> DuckDuckGo</span>
              <span className="signal-pill"><Sparkles size={13} /> ReLU</span>
              <span className="signal-pill"><Compass size={13} /> Firecrawl</span>
            </div>
            <div className="topbar-spacer" />
            <button className="settings-btn" onClick={() => setSettingsOpen(true)}>
              <Settings size={14} /> Settings
            </button>
          </div>

          <div className="messages">
            <div className="messages-inner">
              {messages.length === 0 && !isLoading && (
                <div className="welcome">
                  <div className="welcome-badge">Research-first • Visual • Structured</div>
                  <h1>RAY God Mode</h1>
                  <p>Self-hosted-first Firecrawl, DuckDuckGo for fast search, ReLU reranking for tighter evidence, and visual rendering directly inside chat.</p>
                  <div className="welcome-cards">
                    <div className="welcome-card" onClick={() => quickPrompt('Compare top reasoning models and include a leaderboard chart')}>
                      <div className="wc-title"><ChartColumn size={13} /> Visual Research</div>
                      <div className="wc-desc">Leaderboard with chart rendering</div>
                    </div>
                    <div className="welcome-card" onClick={() => quickPrompt('Research self-hosted Firecrawl vs cloud fallback and summarize it as a document')}>
                      <div className="wc-title"><FlaskConical size={13} /> Deep Research</div>
                      <div className="wc-desc">Document-style research brief</div>
                    </div>
                    <div className="welcome-card" onClick={() => quickPrompt('Design an AI workflow and include a mermaid diagram plus implementation notes')}>
                      <div className="wc-title"><Workflow size={13} /> Architecture</div>
                      <div className="wc-desc">Diagram plus execution canvas</div>
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
                    <span className="message-role">{message.role === 'user' ? 'You' : modelLabel}</span>
                  </div>
                  <div className={`message-body ${message.role === 'user' ? 'user-body' : 'assistant-body'}`}>
                    <StructuredContent content={message.content} />

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

              {isLoading && (
                <div className="message msg-appear">
                  <div className="message-header">
                    <div className="message-avatar assistant">R</div>
                    <span className="message-role">{modelLabel}</span>
                  </div>
                  {!messages.length || messages[messages.length - 1]?.role === 'user' ? (
                    <div className="thinking-block">
                      <div className="thinking-visual">
                        <div className="thinking-bar">
                          <div className="thinking-bar-fill" />
                        </div>
                        <div className="thinking-status">{statusText || `Thinking with ${modelLabel}…`}</div>
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

          <div className="input-area">
            <div className="input-area-inner">
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
                {modelLabel} · {mode} mode · DuckDuckGo basic search · Firecrawl self-hosted first · ReLU reranker
              </div>
            </div>
          </div>
        </div>

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

        {settingsOpen && (
          <div className="modal-overlay" onClick={() => setSettingsOpen(false)}>
            <div className="modal" onClick={event => event.stopPropagation()}>
              <div className="modal-header">
                <h3>Runtime Settings</h3>
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
                    <label className="form-label">Firecrawl Strategy</label>
                    <select
                      className="form-select"
                      value={firecrawlConfig.strategy}
                      onChange={event => setFirecrawlConfig(current => ({ ...current, strategy: event.target.value }))}
                    >
                      <option value="self_hosted_first">Self-hosted first</option>
                      <option value="cloud_only">Cloud only</option>
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
                    <label className="form-label">Firecrawl Fallback Key</label>
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
                  <div className="section-kicker">Research UI Defaults</div>
                  <p>DuckDuckGo handles basic web search, Firecrawl handles deep crawling, research responses prefer document blocks, and the frontend renders charts, canvases, diagrams, and orchestration logs inline.</p>
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn-ghost" onClick={() => setSettingsOpen(false)}>Cancel</button>
                <button className="btn-primary" onClick={saveSettings}>Save</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
