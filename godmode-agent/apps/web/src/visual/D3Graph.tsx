import { useEffect, useRef } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { GraphSpec, THEME_PRESETS, DEFAULT_STYLE, VisualStyle } from "./types"

interface D3GraphProps {
  spec: GraphSpec
  raw?: string
}

export function D3Graph({ spec, raw }: D3GraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const style: VisualStyle = { ...DEFAULT_STYLE, ...spec.style }
  const theme = THEME_PRESETS[style.theme] || THEME_PRESETS["modern-3d-education"]

  useEffect(() => {
    if (!svgRef.current || !spec.data.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()

    const width = 700
    const height = 400
    const margin = { top: 40, right: 40, bottom: 50, left: 60 }
    const innerW = width - margin.left - margin.right
    const innerH = height - margin.top - margin.bottom

    const g = svg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`)

    const xKey = spec.xKey || Object.keys(spec.data[0])[0]
    const yKey = spec.yKey || Object.keys(spec.data[0])[1]
    const sizeKey = spec.sizeKey
    const colorKey = spec.colorKey

    const xValues = spec.data.map((d) => d[xKey] as number).filter((v) => typeof v === "number")
    const yValues = spec.data.map((d) => d[yKey] as number).filter((v) => typeof v === "number")

    if (!xValues.length || !yValues.length) return

    const xScale = d3
      .scaleLinear()
      .domain([d3.min(xValues) || 0, d3.max(xValues) || 1])
      .range([0, innerW])
      .nice()

    const yScale = d3
      .scaleLinear()
      .domain([d3.min(yValues) || 0, d3.max(yValues) || 1])
      .range([innerH, 0])
      .nice()

    const sizeExtent = sizeKey
      ? d3.extent(spec.data.map((d) => (d[sizeKey] as number) || 0)) as [number, number]
      : [4, 20]

    const sizeScale = d3
      .scaleSqrt()
      .domain(sizeExtent)
      .range([4, 20])

    const uniqueCategories = colorKey
      ? Array.from(new Set(spec.data.map((d) => String(d[colorKey]))))
      : []

    const colorScale = d3
      .scaleOrdinal<string>()
      .domain(uniqueCategories)
      .range(d3.schemeTableau10)

    const defaultColor = theme.accent

    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(6).tickSize(-innerH).tickPadding(8))
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) => sel.select(".domain").remove())
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) =>
        sel.selectAll(".tick line").attr("stroke", theme.edgeStroke).attr("stroke-dasharray", "2,4"),
      )
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) =>
        sel.selectAll(".tick text").attr("fill", theme.textSecondary).attr("font-size", 11),
      )

    g.append("g")
      .call(d3.axisLeft(yScale).ticks(6).tickSize(-innerW).tickPadding(8))
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) => sel.select(".domain").remove())
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) =>
        sel.selectAll(".tick line").attr("stroke", theme.edgeStroke).attr("stroke-dasharray", "2,4"),
      )
      .call((sel: d3.Selection<SVGGElement, unknown, null, undefined>) =>
        sel.selectAll(".tick text").attr("fill", theme.textSecondary).attr("font-size", 11),
      )

    const tooltip = d3
      .select("body")
      .append("div")
      .style("position", "absolute")
      .style("padding", "8px 12px")
      .style("background", "rgba(15, 23, 42, 0.95)")
      .style("border", "1px solid rgba(148, 163, 184, 0.2)")
      .style("border-radius", "8px")
      .style("color", theme.text)
      .style("font-size", "12px")
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("backdrop-filter", "blur(8px)")
      .style("z-index", 9999) as unknown as d3.Selection<HTMLDivElement, unknown, null, undefined>

    g.selectAll<SVGCircleElement, Record<string, unknown>>(".dot")
      .data(spec.data)
      .join("circle")
      .attr("class", "dot")
      .attr("cx", (d: Record<string, unknown>) => xScale(d[xKey] as number))
      .attr("cy", (d: Record<string, unknown>) => yScale(d[yKey] as number))
      .attr("r", sizeKey
        ? (d: Record<string, unknown>) => sizeScale(d[sizeKey] as number)
        : 6)
      .attr("fill", (d: Record<string, unknown>) => {
        if (!colorKey) return defaultColor
        const cat = String(d[colorKey])
        return colorScale(cat) || defaultColor
      })
      .attr("fill-opacity", 0.7)
      .attr("stroke", (d: Record<string, unknown>) => {
        if (!colorKey) return defaultColor
        const cat = String(d[colorKey])
        return colorScale(cat) || defaultColor
      })
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.4)
      .style("cursor", "pointer")
      .on("mouseover", function (event: MouseEvent, d: Record<string, unknown>) {
        const currentR = sizeKey ? sizeScale(d[sizeKey] as number) : 6
        d3.select<SVGCircleElement, Record<string, unknown>>(this)
          .transition()
          .duration(150)
          .attr("r", currentR + 4)
          .attr("fill-opacity", 1)
        const tooltipHtml = Object.entries(d)
          .map(([k, v]) => `<strong>${k}:</strong> ${v}`)
          .join("<br/>")
        tooltip
          .transition()
          .duration(150)
          .style("opacity", 1)
          .each(function() {
            d3.select(this as HTMLDivElement).html(tooltipHtml)
          })
      })
      .on("mousemove", function (event: MouseEvent) {
        d3.select(this)
        tooltip
          .style("left", `${event.pageX + 12}px`)
          .style("top", `${event.pageY - 28}px`)
      })
      .on("mouseout", function (event: MouseEvent, d: Record<string, unknown>) {
        const currentR = sizeKey ? sizeScale(d[sizeKey] as number) : 6
        d3.select<SVGCircleElement, Record<string, unknown>>(this)
          .transition()
          .duration(150)
          .attr("r", currentR)
          .attr("fill-opacity", 0.7)
        tooltip.transition().duration(150).style("opacity", 0)
      })

    if (xKey) {
      g.append("text")
        .attr("x", innerW / 2)
        .attr("y", innerH + 40)
        .attr("text-anchor", "middle")
        .attr("fill", theme.textSecondary)
        .attr("font-size", 12)
        .text(xKey)
    }
    if (yKey) {
      g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -innerH / 2)
        .attr("y", -45)
        .attr("text-anchor", "middle")
        .attr("fill", theme.textSecondary)
        .attr("font-size", 12)
        .text(yKey)
    }

    return () => {
      tooltip.remove()
    }
  }, [spec.data, spec.xKey, spec.yKey, spec.sizeKey, spec.colorKey, style.theme, theme])

  return (
    <div className="d3-graph-container" style={{ background: theme.bg }}>
      <div className="d3-graph-header">
        <h3>{spec.title}</h3>
        {spec.subtitle && <p>{spec.subtitle}</p>}
      </div>
      <svg ref={svgRef} style={{ width: "100%", height: 400, display: "block" }} />
    </div>
  )
}
