import { useCallback, useEffect, useMemo, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  MarkerType,
  Position,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { motion, AnimatePresence } from "framer-motion"
import {
  DiagramSpec,
  VisualNode,
  VisualEdge,
  VisualStyle,
  DEFAULT_STYLE,
  GROUP_COLORS,
  THEME_PRESETS,
} from "./types"
import { CustomNode } from "./CustomNode"
import { CustomEdge } from "./CustomEdge"

const nodeTypes = { custom: CustomNode } as const
const edgeTypes = { custom: CustomEdge } as const

function computeLayout(nodes: VisualNode[], edges: VisualEdge[], style: VisualStyle): { nodes: Node[]; edges: Edge[] } {
  const theme = THEME_PRESETS[style.theme] || THEME_PRESETS["modern-3d-education"]
  const flowNodes: Node[] = []
  const flowEdges: Edge[] = []

  const nodeMap = new Map<string, VisualNode>()
  for (const n of nodes) nodeMap.set(n.id, n)

  const inDegree = new Map<string, number>()
  const adj = new Map<string, string[]>()
  for (const n of nodes) {
    inDegree.set(n.id, 0)
    adj.set(n.id, [])
  }
  for (const e of edges) {
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1)
    adj.get(e.source)?.push(e.target)
  }

  const levels = new Map<string, number>()
  const queue: string[] = []
  for (const n of nodes) {
    if ((inDegree.get(n.id) || 0) === 0) {
      queue.push(n.id)
      levels.set(n.id, 0)
    }
  }
  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLevel = levels.get(current)!
    for (const child of adj.get(current) || []) {
      levels.set(child, Math.max(levels.get(child) || 0, currentLevel + 1))
      inDegree.set(child, inDegree.get(child)! - 1)
      if (inDegree.get(child) === 0) queue.push(child)
    }
  }
  for (const n of nodes) {
    if (!levels.has(n.id)) levels.set(n.id, 0)
  }

  const levelGroups = new Map<number, string[]>()
  for (const [id, level] of levels) {
    if (!levelGroups.has(level)) levelGroups.set(level, [])
    levelGroups.get(level)!.push(id)
  }

  const nodeWidth = 248
  const levelGapX = 340
  const nodeGapY = 36

  for (const [level, ids] of levelGroups) {
    const orderedIds = [...ids].sort((a, b) => {
      const aNode = nodeMap.get(a)
      const bNode = nodeMap.get(b)
      return (bNode?.weight || 0) - (aNode?.weight || 0)
    })
    const nodeHeights = orderedIds.map((id) => nodeMap.get(id)?.description ? 112 : 92)
    const totalHeight = nodeHeights.reduce((sum, height) => sum + height, 0) + Math.max(0, orderedIds.length - 1) * nodeGapY
    const startY = -totalHeight / 2
    let currentY = startY
    orderedIds.forEach((id, index) => {
      const node = nodeMap.get(id)!
      const x = level * levelGapX
      const nodeHeight = node.description ? 112 : 92
      const y = currentY
      const groupColor = GROUP_COLORS[node.type] || GROUP_COLORS.concept
      const entranceDelay = (level * 0.18) + (index * 0.08)

      flowNodes.push({
        id,
        type: "custom",
        position: { x, y },
        data: {
          label: node.label,
          nodeType: node.type,
          group: node.group,
          description: node.description,
          detail: node.detail,
          icon: node.icon,
          color: node.color || groupColor,
          entranceDelay,
          weight: node.weight,
          metadata: node.metadata,
          theme,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          width: nodeWidth,
          minWidth: nodeWidth,
          minHeight: nodeHeight,
        },
      })
      currentY += nodeHeight + nodeGapY
    })
  }

  for (const e of edges) {
    flowEdges.push({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: e.type === "smoothstep" ? "smoothstep" : e.type === "step" ? "step" : e.type === "straight" ? "default" : "custom",
      label: e.label,
      animated: e.animated ?? true,
      markerEnd: { type: MarkerType.ArrowClosed, width: 20, height: 20, color: theme.edgeStroke },
      style: {
        stroke: theme.edgeStroke,
        strokeWidth: 2,
      },
      data: {
        description: e.description,
        style: e.style,
      },
    })
  }

  return { nodes: flowNodes, edges: flowEdges }
}

interface FlowDiagramProps {
  spec: DiagramSpec
  raw?: string
  interactive?: boolean
}

export function FlowDiagram({ spec, raw, interactive = true }: FlowDiagramProps) {
  const style: VisualStyle = { ...DEFAULT_STYLE, ...spec.style }
  const { nodes: flowNodes, edges: flowEdges } = useMemo(
    () => computeLayout(spec.nodes, spec.edges, style),
    [spec.nodes, spec.edges, style],
  )

  const [rfNodes, setRfNodes] = useState<Node[]>(flowNodes)
  const [rfEdges, setRfEdges] = useState<Edge[]>(flowEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  useEffect(() => {
    setRfNodes(flowNodes)
    setRfEdges(flowEdges)
    setSelectedNode(null)
  }, [flowEdges, flowNodes])

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setRfNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  )
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setRfEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )
  const onConnect: OnConnect = useCallback(
    (connection) => setRfEdges((eds) => addEdge(connection, eds)),
    [],
  )

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const theme = THEME_PRESETS[style.theme] || THEME_PRESETS["modern-3d-education"]

  return (
    <div className="flow-diagram-container" style={{ background: theme.bg }}>
      <div className="flow-diagram-header">
        <div className="flow-diagram-title">
          <h3>{spec.title}</h3>
          {spec.subtitle && <p>{spec.subtitle}</p>}
        </div>
        <div className="flow-diagram-legend">
          {spec.legend?.map((item) => (
            <span key={item.label} className="flow-legend-item">
              <span className="flow-legend-dot" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      </div>

      <div className="flow-diagram-canvas" style={{ height: 520 }}>
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={interactive ? onNodesChange : undefined}
          onEdgesChange={interactive ? onEdgesChange : undefined}
          onConnect={interactive ? onConnect : undefined}
          onNodeClick={interactive ? onNodeClick : undefined}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.24 }}
          minZoom={0.2}
          maxZoom={2}
          nodesDraggable={interactive}
          elementsSelectable={interactive}
          nodesConnectable={false}
          panOnDrag={interactive}
          defaultEdgeOptions={{
            markerEnd: { type: MarkerType.ArrowClosed, width: 20, height: 20 },
          }}
        >
          <Background color={theme.edgeStroke} gap={24} size={1} />
          <Controls showInteractive={interactive} />
          <MiniMap
            nodeColor={(node) => {
              const color = (node.data as { color?: string })?.color
              return color || theme.accent
            }}
            maskColor={theme.bg}
            pannable
            zoomable
          />
        </ReactFlow>
      </div>

      <AnimatePresence>
        {selectedNode && interactive && (
          <motion.div
            className="flow-node-detail-panel"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
          >
            <button className="flow-detail-close" onClick={() => setSelectedNode(null)}>
              ×
            </button>
            <h4>{(selectedNode.data as { label: string }).label}</h4>
            <span className="flow-detail-type">{(selectedNode.data as { nodeType: string }).nodeType}</span>
            {(selectedNode.data as { description?: string }).description && (
              <p>{(selectedNode.data as { description: string }).description}</p>
            )}
            {(selectedNode.data as { detail?: string }).detail && (
              <div className="flow-detail-content">
                {(selectedNode.data as { detail: string }).detail}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
