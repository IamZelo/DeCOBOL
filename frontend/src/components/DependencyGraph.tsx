import { useEffect, useMemo, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { DependencyGraph, GraphNodeCategory } from '../lib/dependencyGraph'

const EDGE_COLOR: Record<string, string> = {
  contains: 'var(--dot-idle)',
  performs: 'var(--accent)',
  copy: 'var(--accent-yellow)',
  file: 'var(--accent-cyan)',
  sql: 'var(--accent-green)',
}

/** Node styling by category — standard procedure / agent-refactored / external I/O. */
export const CATEGORY_STYLE: Record<
  GraphNodeCategory,
  { stroke: string; fill: string; text: string; label: string }
> = {
  standard: {
    stroke: 'var(--text-dim)',
    fill: 'var(--bg-control)',
    text: 'var(--text)',
    label: 'Standard Procedure',
  },
  agent: {
    stroke: 'var(--accent-cyan)',
    fill: 'color-mix(in srgb, var(--accent-cyan) 14%, var(--bg-raised))',
    text: 'var(--accent-cyan)',
    label: 'Agent Refactored',
  },
  external: {
    stroke: 'var(--accent-yellow)',
    fill: 'color-mix(in srgb, var(--accent-yellow) 14%, var(--bg-raised))',
    text: 'var(--accent-yellow)',
    label: 'Database I/O',
  },
}

interface CategoryNodeData extends Record<string, unknown> {
  label: string
  sublabel?: string
  category: GraphNodeCategory
  isHovered: boolean
}

const HANDLE_STYLE = { opacity: 0, pointerEvents: 'none' as const }

function CategoryNode({ data }: NodeProps<Node<CategoryNodeData>>) {
  const style = CATEGORY_STYLE[data.category]
  return (
    <div
      className="depgraph-node"
      style={{
        background: style.fill,
        borderColor: style.stroke,
        borderWidth: data.isHovered ? 2 : 1.25,
      }}
    >
      <Handle type="target" position={Position.Left} style={HANDLE_STYLE} />
      <div className="depgraph-node-label" style={{ color: style.text }}>
        {data.label}
      </div>
      {data.sublabel ? <div className="depgraph-node-sublabel">{data.sublabel}</div> : null}
      <Handle type="source" position={Position.Right} style={HANDLE_STYLE} />
    </div>
  )
}

const NODE_TYPES = { category: CategoryNode }

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

  const initialNodes: Node<CategoryNodeData>[] = useMemo(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: 'category',
        position: { x: n.x, y: n.y },
        data: { label: n.label, sublabel: n.sublabel, category: n.category, isHovered: false },
        style: { width: n.w },
        connectable: false,
      })),
    [graph.nodes],
  )

  const initialEdges: Edge[] = useMemo(
    () =>
      graph.edges.map((e, i) => {
        const to = byId.get(e.to)
        const color = EDGE_COLOR[e.kind]
        return {
          id: `e${i}`,
          source: e.from,
          target: e.to,
          type: 'smoothstep',
          pathOptions: { borderRadius: 12 },
          style: {
            stroke: color,
            strokeWidth: e.kind === 'performs' ? 1.5 : 1.25,
            strokeDasharray: to?.category === 'external' ? '4 3' : undefined,
            transition: 'opacity 120ms ease',
          },
          markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        }
      }),
    [graph.edges, byId],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes])
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges])

  useEffect(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, isHovered: n.id === hovered },
        style: { ...n.style, opacity: !connected || connected.nodes.has(n.id) ? 1 : 0.25 },
      })),
    )
  }, [hovered, connected, setNodes])

  useEffect(() => {
    setEdges((prev) =>
      prev.map((e, i) => ({
        ...e,
        style: { ...e.style, opacity: !connected || connected.edges.has(i) ? 0.9 : 0.12 },
      })),
    )
  }, [connected, setEdges])

  return (
    <div className="depgraph-flow">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={NODE_TYPES}
        onNodeMouseEnter={(_, node) => setHovered(node.id)}
        onNodeMouseLeave={() => setHovered(null)}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.25}
        maxZoom={2}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        aria-label="COBOL program dependency graph — hover a node to trace its connections"
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--line)" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => CATEGORY_STYLE[(node.data as CategoryNodeData).category].stroke}
          maskColor="color-mix(in srgb, var(--bg) 65%, transparent)"
        />
      </ReactFlow>
    </div>
  )
}
