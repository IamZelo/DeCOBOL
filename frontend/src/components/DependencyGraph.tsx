import type { DependencyGraph, GraphNode } from '../lib/dependencyGraph'

const EDGE_COLOR: Record<string, string> = {
  contains: '#4f535d',
  performs: '#d29922',
  copy: '#9c8f7b',
  file: '#9296a0',
  sql: '#6d8fb0',
}

const NODE_FILL: Record<GraphNode['kind'], string> = {
  program: '#181a1f',
  paragraph: '#16181d',
  copybook: '#111318',
  file: '#111318',
  table: '#111318',
}

const NODE_STROKE: Record<GraphNode['kind'], string> = {
  program: '#d29922',
  paragraph: '#34373d',
  copybook: '#4f535d',
  file: '#34373d',
  table: '#6d8fb0',
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
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))

  return (
    <div className="depgraph-scroll">
      <svg
        width={graph.width}
        height={graph.height}
        viewBox={`0 0 ${graph.width} ${graph.height}`}
        role="img"
        aria-label="COBOL program dependency graph"
      >
        {graph.edges.map((edge, i) => {
          const from = byId.get(edge.from)
          const to = byId.get(edge.to)
          if (!from || !to) return null
          const d = edge.kind === 'performs' ? performPath(from, to) : edgePath(from, to)
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={EDGE_COLOR[edge.kind]}
              strokeWidth={edge.kind === 'performs' ? 1.25 : 1}
              strokeDasharray={edge.kind === 'sql' || edge.kind === 'copy' ? '3 2' : undefined}
              opacity={0.85}
            />
          )
        })}

        {graph.nodes.map((node) => (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={node.w}
              height={node.h}
              rx={2}
              fill={NODE_FILL[node.kind]}
              stroke={NODE_STROKE[node.kind]}
              strokeWidth={node.kind === 'program' ? 1.5 : 1}
            />
            <text
              x={node.x + 8}
              y={node.y + node.h / 2 + (node.sublabel ? -3 : 4)}
              fontFamily="'Space Mono', monospace"
              fontSize={11}
              fill="#e2e2e8"
            >
              {node.label.length > 34 ? `${node.label.slice(0, 33)}…` : node.label}
            </text>
            {node.sublabel ? (
              <text
                x={node.x + 8}
                y={node.y + node.h / 2 + 10}
                fontFamily="'Space Mono', monospace"
                fontSize={9}
                fill="#9296a0"
              >
                {node.sublabel}
              </text>
            ) : null}
          </g>
        ))}
      </svg>
    </div>
  )
}
