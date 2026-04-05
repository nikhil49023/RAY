import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { motion } from "framer-motion"
import {
  Zap,
  Database,
  Brain,
  GitBranch,
  FileText,
  Settings,
  Lightbulb,
  Layers,
} from "lucide-react"

const NODE_TYPE_ICONS: Record<string, React.ElementType> = {
  input: Database,
  process: Settings,
  output: FileText,
  concept: Lightbulb,
  decision: GitBranch,
  data: Database,
  function: Zap,
  system: Brain,
}

interface CustomNodeData {
  label: string
  nodeType: string
  entranceDelay?: number
  group?: string
  description?: string
  detail?: string
  icon?: string
  color: string
  weight?: number
  metadata?: Record<string, unknown>
  theme: {
    bg: string
    nodeBg: string
    nodeBorder: string
    text: string
    textSecondary: string
    edgeStroke: string
    accent: string
    shadow: string
  }
}

export const CustomNode = memo(({ data }: NodeProps) => {
  const typedData = data as unknown as CustomNodeData
  const { label, nodeType, color, theme, entranceDelay = 0 } = typedData
  const Icon = NODE_TYPE_ICONS[nodeType] || Layers

  return (
    <motion.div
      className="custom-node"
      initial={{ opacity: 0, y: 60, scale: 0.82, filter: 'blur(10px)' }}
      animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
      transition={{
        type: 'spring',
        stiffness: 120,
        damping: 14,
        mass: 0.8,
        delay: entranceDelay,
      }}
      whileHover={{ scale: 1.03, y: -2 }}
      style={{
        background: theme.nodeBg,
        border: `1px solid ${theme.nodeBorder}`,
        borderRadius: 12,
        padding: "12px 16px",
        minWidth: 200,
        boxShadow: theme.shadow,
        backdropFilter: "blur(8px)",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color, width: 8, height: 8, border: "2px solid rgba(13, 13, 18, 0.8)" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: `${color}15`,
            border: `1px solid ${color}25`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon size={16} color={color} strokeWidth={1.5} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: theme.text,
              fontWeight: 500,
              fontSize: 13,
              lineHeight: 1.3,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {label}
          </div>
          <div
            style={{
              color: `${color}BB`,
              fontSize: 10,
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: 0.8,
              marginTop: 3,
            }}
          >
            {nodeType}
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: color, width: 8, height: 8, border: "2px solid rgba(13, 13, 18, 0.8)" }} />
    </motion.div>
  )
})

CustomNode.displayName = "CustomNode"
