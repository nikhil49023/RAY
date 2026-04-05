import { memo } from "react"
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getSmoothStepPath } from "@xyflow/react"
import { motion } from "framer-motion"

export const CustomEdge = memo((props: EdgeProps) => {
  const {
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    label,
  } = props

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 16,
  })

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={{ strokeWidth: 2, ...style }} />
      {label && (
        <EdgeLabelRenderer>
          <motion.div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
              background: "rgba(15, 23, 42, 0.85)",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              borderRadius: 6,
              padding: "3px 8px",
              fontSize: 11,
              color: "#94A3B8",
              whiteSpace: "nowrap",
              backdropFilter: "blur(4px)",
            }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2, delay: 0.3 }}
          >
            {label}
          </motion.div>
        </EdgeLabelRenderer>
      )}
    </>
  )
})

CustomEdge.displayName = "CustomEdge"
