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
  copybook: {
    stroke: 'var(--accent-green)',
    fill: 'color-mix(in srgb, var(--accent-green) 14%, var(--bg-raised))',
    text: 'var(--accent-green)',
    label: 'Copybook in workspace',
  },
  missing: {
    stroke: 'var(--accent-yellow)',
    fill: 'transparent',
    text: 'var(--accent-yellow)',
    label: 'Unresolved (not in workspace)',
  },
  data: {
    stroke: 'var(--accent-cyan)',
    fill: 'color-mix(in srgb, var(--accent-cyan) 10%, var(--bg-raised))',
    text: 'var(--accent-cyan)',
    label: 'Dataset / DD name',
  },
}

interface CategoryNodeData extends Record<string, unknown> {
  label: string
  sublabel?: string
  category: GraphNodeCategory
  isHovered: boolean
  isActive: boolean
}

const HANDLE_STYLE = { opacity: 0, pointerEvents: 'none' as const }

/**
 * Four handles per node, so an edge can pick its side: the repo graph routes
 * program -> table downward into the table band and everything else across.
 */
function NodeHandles() {
  return (
    <>
      <Handle id="tl" type="target" position={Position.Left} style={HANDLE_STYLE} />
      <Handle id="tt" type="target" position={Position.Top} style={HANDLE_STYLE} />
      <Handle id="sr" type="source" position={Position.Right} style={HANDLE_STYLE} />
      <Handle id="sb" type="source" position={Position.Bottom} style={HANDLE_STYLE} />
    </>
  )
}

/** The merge point itself — a dot, sized by the layout, with no label. */
function JunctionNode({ data }: NodeProps<Node<CategoryNodeData>>) {
  return (
    <div
      className="depgraph-junction"
      style={{ borderColor: CATEGORY_STYLE[data.category].stroke }}
    >
      <NodeHandles />
    </div>
  )
}

function CategoryNode({ data }: NodeProps<Node<CategoryNodeData>>) {
  const style = CATEGORY_STYLE[data.category]
  return (
    <div
      className="depgraph-node"
      style={{
        background: style.fill,
        borderColor: data.isActive ? 'var(--accent)' : style.stroke,
        borderWidth: data.isHovered || data.isActive ? 2 : 1.25,
        borderStyle: data.category === 'missing' ? 'dashed' : 'solid',
      }}
    >
      <NodeHandles />
      <div className="depgraph-node-label" style={{ color: style.text }}>
        {data.label}
      </div>
      {data.sublabel ? <div className="depgraph-node-sublabel">{data.sublabel}</div> : null}
    </div>
  )
}

const NODE_TYPES = { category: CategoryNode, junction: JunctionNode }

export function DependencyGraphView({
  graph,
  onNodeClick,
}: {
  graph: DependencyGraph
  /** Called with the clicked node's id — used to open a file from the graph. */
  onNodeClick?: (id: string) => void
}) {
  const [hovered, setHovered] = useState<string | null>(null)
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph])
  const junctions = useMemo(
    () => new Set(graph.nodes.filter((n) => n.kind === 'junction').map((n) => n.id)),
    [graph.nodes],
  )

  const connected = useMemo(() => {
    if (!hovered) return null
    const ids = new Set<string>([hovered])
    const edgeIdx = new Set<number>()
    // Two passes, so hovering either side of a merged fan-in still traces the
    // whole path: the first reaches the junction, the second goes through it.
    for (let pass = 0; pass < 2; pass += 1) {
      graph.edges.forEach((edge, i) => {
        const touches = ids.has(edge.from) || ids.has(edge.to)
        if (!touches) return
        const viaJunction =
          pass === 0 ? edge.from === hovered || edge.to === hovered : junctions.has(edge.from) || junctions.has(edge.to)
        if (!viaJunction) return
        edgeIdx.add(i)
        ids.add(edge.from)
        ids.add(edge.to)
      })
    }
    return { nodes: ids, edges: edgeIdx }
  }, [hovered, graph.edges, junctions])

  const initialNodes: Node<CategoryNodeData>[] = useMemo(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: n.kind === 'junction' ? 'junction' : 'category',
        position: { x: n.x, y: n.y },
        data: {
          label: n.label,
          sublabel: n.sublabel,
          category: n.category,
          isHovered: false,
          isActive: n.active === true,
        },
        style: n.kind === 'junction' ? { width: n.w, height: n.h } : { width: n.w },
        selectable: n.kind !== 'junction',
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
          sourceHandle: e.sourceHandle ?? 'sr',
          targetHandle: e.targetHandle ?? 'tl',
          type: 'smoothstep',
          label: e.label,
          // Labels sit on top of edges and nodes alike, so they carry the panel
          // background rather than relying on empty space being there.
          labelShowBg: true,
          labelBgStyle: { fill: 'var(--bg-panel)', fillOpacity: 0.92 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 3,
          labelStyle: { fill: 'var(--text-dim)', fontSize: 10 },
          pathOptions: { borderRadius: 12, offset: e.offset },
          style: {
            stroke: color,
            strokeWidth: e.kind === 'performs' ? 1.5 : 1.25,
            strokeDasharray: to?.category === 'external' ? '4 3' : undefined,
            transition: 'opacity 120ms ease',
          },
          // A hop into a junction has no arrow head — the merged line past the
          // junction carries the single arrow into the target.
          markerEnd: e.merged
            ? undefined
            : { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
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
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
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
