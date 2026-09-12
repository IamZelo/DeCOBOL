import { useMemo, useState } from 'react'
import type { DependencyGraph, GraphNode } from '../lib/dependencyGraph'

const EDGE_COLOR: Record<string, string> = {
  contains: 'var(--dot-idle)',
  performs: 'var(--accent)',
  copy: 'var(--accent-yellow)',
  file: 'var(--accent-cyan)',
  sql: 'var(--accent-green)',
}

const NODE_STROKE: Record<GraphNode['kind'], string> = {
  program: 'var(--accent)',
  paragraph: 'var(--dot-idle)',
  copybook: 'var(--accent-yellow)',
  file: 'var(--accent-cyan)',
  table: 'var(--accent-green)',
}

function edgePath(from: GraphNode, to: GraphNode): string {
  const x1 = from.x + from.w
  const y1 = from.y + from.h / 2
  const x2 = to.x
  const y2 = to.y + to.h / 2
  const midX = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
}

/** Same-column PERFORM edges arc out to the right and back. */
function performPath(from: GraphNode, to: GraphNode): string {
  const x = from.x + from.w
  const y1 = from.y + from.h / 2
  const y2 = to.y + to.h / 2
  const bow = Math.min(28, Math.max(14, Math.abs(y2 - y1) / 4))
  return `M ${x} ${y1} C ${x + bow} ${y1}, ${x + bow} ${y2}, ${x} ${y2}`
}

export function DependencyGraphView({ graph }: { graph: DependencyGraph }) {
  const [hovered, setHovered] = useState<string | null>(null)
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph])

  const connected = useMemo(() => {
    if (!hovered) return null
    const ids = new Set<string>([hovered])
    const edgeIdx = new Set<number>()
    graph.edges.forEach((edge, i) => {
      if (edge.from === hovered || edge.to === hovered) {
        edgeIdx.add(i)
        ids.add(edge.from)
        ids.add(edge.to)
      }
    })
    return { nodes: ids, edges: edgeIdx }
  }, [hovered, graph.edges])

  return (
    <div className="depgraph-scroll">
      <svg
        width={graph.width}
        height={graph.height}
        viewBox={`0 0 ${graph.width} ${graph.height}`}
        role="img"
        aria-label="COBOL program dependency graph — hover a node to trace its connections"
      >
        {graph.edges.map((edge, i) => {
          const from = byId.get(edge.from)
          const to = byId.get(edge.to)
          if (!from || !to) return null
          const d = edge.kind === 'performs' ? performPath(from, to) : edgePath(from, to)
          const active = !connected || connected.edges.has(i)
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={EDGE_COLOR[edge.kind]}
              strokeWidth={edge.kind === 'performs' ? 1.25 : 1}
              strokeDasharray={edge.kind === 'sql' || edge.kind === 'copy' ? '3 2' : undefined}
              opacity={active ? 0.9 : 0.12}
              style={{ transition: 'opacity 120ms ease' }}
            />
          )
        })}

        {graph.nodes.map((node) => {
          const active = !connected || connected.nodes.has(node.id)
          const isHovered = node.id === hovered
          return (
            <g
              key={node.id}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer' }}
              opacity={active ? 1 : 0.3}
            >
              <rect
                x={node.x}
                y={node.y}
                width={node.w}
                height={node.h}
                rx={6}
                fill={isHovered ? 'var(--bg-control)' : 'var(--bg-raised)'}
                stroke={NODE_STROKE[node.kind]}
                strokeWidth={isHovered ? 2 : node.kind === 'program' ? 1.5 : 1}
                style={{ transition: 'fill 120ms ease, stroke-width 120ms ease' }}
              />
              <text
                x={node.x + 8}
                y={node.y + node.h / 2 + (node.sublabel ? -3 : 4)}
                fontFamily="'Space Mono', monospace"
                fontSize={11}
                fill="var(--text)"
              >
                {node.label.length > 34 ? `${node.label.slice(0, 33)}…` : node.label}
              </text>
              {node.sublabel ? (
                <text
                  x={node.x + 8}
                  y={node.y + node.h / 2 + 10}
                  fontFamily="'Space Mono', monospace"
                  fontSize={9}
                  fill="var(--text-dim)"
                >
                  {node.sublabel}
                </text>
              ) : null}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
