import type { RepoEdgeKind, RepoGraphNode, RepoGraphPayload } from '../types'
import type { DependencyGraph, GraphEdge, GraphNode, GraphNodeCategory } from './dependencyGraph'

const NODE_H = 44
const ROW_H = 76
const COL_W = 240
const COL_GAP = 130
const PAD = 24
/** Vertical gap between the program band and the table band below it. */
const BAND_GAP = 100
const JUNCTION_SIZE = 10
/** Keeps descent lanes clear of both columns they run between. */
const LANE_INSET = 26
/** A target with at least this many incoming edges of one kind gets a junction. */
const MERGE_THRESHOLD = 2

const CATEGORY_BY_KIND: Record<RepoGraphNode['kind'], GraphNodeCategory> = {
  program: 'standard',
  copybook: 'copybook',
  missing_program: 'missing',
  missing_copybook: 'missing',
  table: 'external',
  dataset: 'data',
}

export interface RepoDependencyGraph extends DependencyGraph {
  /** Node id -> workspace-relative path, for click-to-open. */
  pathById: Map<string, string>
  /** Kinds actually present, so the legend only lists what is drawn. */
  categories: GraphNodeCategory[]
  edgeKinds: RepoEdgeKind[]
  fileCount: number
  parseErrors: { path: string; error: string }[]
}

/**
 * Lays out the whole-workspace scan (`GET /api/fs/graph`) as a band of
 * left-to-right data flow with the database underneath it:
 *
 *   input datasets │ programs (by CALL depth) │ copybooks + subprograms │ output datasets
 *   ───────────────┴──────────── DB2 tables, on their own row below ────┴────────────────
 *
 * The tables sit in a separate band because they are the densest nodes in the
 * graph — every program touches several, and routing those edges sideways
 * through the copybook column is what made the single-band layout unreadable.
 *
 * Where many sources reach one target (five programs including the same
 * `SQLCA`, say), the edges are merged through a junction node placed just
 * before the target, so the fan-in arrives as one line rather than N lines
 * crossing every column in between.
 */
export function buildRepoGraph(
  payload: RepoGraphPayload,
  activePath?: string | null,
): RepoDependencyGraph {
  const byId = new Map(payload.nodes.map((n) => [n.id, n]))
  const depth = callDepths(payload)

  // A dataset a program reads is upstream of it (edge dataset -> program) and
  // belongs on the left; one a program writes is downstream, on the right.
  const writtenDatasets = new Set(
    payload.edges
      .filter((e) => e.kind === 'file' && byId.get(e.to)?.kind === 'dataset')
      .map((e) => e.to),
  )

  const maxDepth = Math.max(
    0,
    ...payload.nodes.filter((n) => n.kind === 'program').map((n) => depth.get(n.id) ?? 0),
  )
  const dependencyColumn = maxDepth + 2
  const outputColumn = dependencyColumn + 1

  function columnOf(n: RepoGraphNode): number {
    switch (n.kind) {
      case 'dataset':
        return writtenDatasets.has(n.id) ? outputColumn : 0
      case 'program':
        return 1 + (depth.get(n.id) ?? 0)
      default:
        return dependencyColumn
    }
  }

  const tables = payload.nodes.filter((n) => n.kind === 'table')
  const banded = payload.nodes.filter((n) => n.kind !== 'table')

  // Column members, each ordered so the heaviest nodes sit in the middle of
  // their column — that keeps the long edges near the vertical centre of the
  // canvas instead of sweeping across the whole height.
  const columns = new Map<number, RepoGraphNode[]>()
  for (const n of banded) {
    const col = columnOf(n)
    const list = columns.get(col) ?? []
    list.push(n)
    columns.set(col, list)
  }
  for (const list of columns.values()) {
    list.sort((a, b) => a.label.localeCompare(b.label))
  }

  const tallest = Math.max(1, ...[...columns.values()].map((l) => l.length))
  const bandHeight = tallest * ROW_H

  const placed = new Map<string, GraphNode>()
  for (const [col, list] of columns) {
    // Centre each column vertically against the tallest one.
    const offset = (bandHeight - list.length * ROW_H) / 2
    list.forEach((n, row) => {
      placed.set(n.id, {
        id: n.id,
        kind: graphKind(n.kind),
        category: CATEGORY_BY_KIND[n.kind],
        label: n.label,
        sublabel: n.sublabel,
        x: PAD + col * (COL_W + COL_GAP),
        y: PAD + offset + row * ROW_H,
        w: COL_W,
        h: NODE_H,
        active: activePath != null && n.path === activePath,
      })
    })
  }

  // The table band: one row under the programs, spread across the full width
  // so each table sits roughly beneath the programs that use it.
  const bandBottom = PAD + bandHeight
  const tableY = bandBottom + BAND_GAP
  const tableSpan = Math.max(columns.size, 1)
  // Half a column to the right of the band's grid, so an edge dropping into a
  // table runs down the gap between two columns instead of through them.
  const tableShift = (COL_W + COL_GAP) / 2
  tables.forEach((n, i) => {
    const slot = tables.length > 1 ? (i * (tableSpan - 1)) / (tables.length - 1) : (tableSpan - 1) / 2
    placed.set(n.id, {
      id: n.id,
      kind: 'table',
      category: CATEGORY_BY_KIND[n.kind],
      label: n.label,
      sublabel: n.sublabel,
      x: PAD + tableShift + slot * (COL_W + COL_GAP),
      y: tableY,
      w: COL_W,
      h: NODE_H,
      active: false,
    })
  })

  const { nodes: junctions, edges } = routeEdges(payload, placed, byId)

  const nodes = [...placed.values(), ...junctions]
  const width =
    PAD * 2 + (tables.length ? tableShift : 0) + tableSpan * COL_W + (tableSpan - 1) * COL_GAP
  const height = (tables.length ? tableY + NODE_H : bandBottom) + PAD

  return {
    nodes,
    edges,
    width,
    height,
    pathById: new Map(
      payload.nodes.filter((n) => n.path).map((n) => [n.id, n.path as string]),
    ),
    categories: [...new Set([...placed.values()].map((n) => n.category))],
    edgeKinds: [...new Set(payload.edges.map((e) => e.kind))],
    fileCount: payload.file_count,
    parseErrors: payload.parse_errors,
  }
}

function graphKind(kind: RepoGraphNode['kind']): GraphNode['kind'] {
  if (kind === 'dataset') return 'file'
  if (kind === 'table') return 'table'
  if (kind === 'copybook' || kind === 'missing_copybook') return 'copybook'
  return 'program'
}

/**
 * Turns the payload's edges into laid-out edges, merging every fan-in of
 * `MERGE_THRESHOLD` or more same-kind edges through a junction node.
 *
 * Edges into the table band leave the bottom of their source and enter the top
 * of the table; everything else runs left to right.
 */
function routeEdges(
  payload: RepoGraphPayload,
  placed: Map<string, GraphNode>,
  byId: Map<string, RepoGraphNode>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const fanIn = new Map<string, typeof payload.edges>()
  for (const e of payload.edges) {
    const key = `${e.to}|${e.kind}`
    fanIn.set(key, [...(fanIn.get(key) ?? []), e])
  }

  // Each program that reaches the table band gets its own descent lane in the
  // gap to the right of its column, so the vertical runs neither overlap each
  // other nor cross the nodes stacked below their source.
  const lanes = new Map<string, number>()
  const toTables = payload.edges.filter((e) => byId.get(e.to)?.kind === 'table')
  ;[...new Set(toTables.map((e) => e.from))]
    .sort((a, b) => (placed.get(a)?.y ?? 0) - (placed.get(b)?.y ?? 0))
    .forEach((id, i, all) => {
      lanes.set(id, LANE_INSET + (i * (COL_GAP - 2 * LANE_INSET)) / Math.max(all.length - 1, 1))
    })

  const junctions: GraphNode[] = []
  const edges: GraphEdge[] = []

  for (const [key, group] of fanIn) {
    const [targetId, kind] = [group[0].to, group[0].kind]
    const target = placed.get(targetId)
    if (!target) continue
    // Table edges leave the right of their source, drop down the lane gap, and
    // enter the table from above; everything else runs straight across.
    const vertical = byId.get(targetId)?.kind === 'table'
    const enter = vertical ? ('tt' as const) : ('tl' as const)
    const laneOf = (from: string) => (vertical ? lanes.get(from) : undefined)

    if (group.length < MERGE_THRESHOLD) {
      for (const e of group) {
        edges.push({
          from: e.from,
          to: e.to,
          kind: edgeKind(kind),
          label: edgeLabel(kind, e.label),
          sourceHandle: 'sr',
          targetHandle: enter,
          offset: laneOf(e.from),
        })
      }
      continue
    }

    // One junction per (target, kind): the fan-in collapses to a single point
    // and only the last hop carries the arrow head and the label.
    const junctionId = `junction:${key}`
    junctions.push({
      id: junctionId,
      kind: 'junction',
      category: target.category,
      label: '',
      x: vertical
        ? target.x + target.w / 2 - JUNCTION_SIZE / 2
        // Far enough back from the target that the edge label sitting on the
        // last hop has room and does not land on the node itself.
        : target.x - COL_GAP * 0.8 - JUNCTION_SIZE / 2,
      y: vertical ? target.y - BAND_GAP / 2 : target.y + target.h / 2 - JUNCTION_SIZE / 2,
      w: JUNCTION_SIZE,
      h: JUNCTION_SIZE,
    })

    for (const e of group) {
      edges.push({
        from: e.from,
        to: junctionId,
        kind: edgeKind(kind),
        sourceHandle: 'sr',
        targetHandle: vertical ? 'tt' : 'tl',
        merged: true,
        offset: laneOf(e.from),
      })
    }
    edges.push({
      from: junctionId,
      to: targetId,
      kind: edgeKind(kind),
      label: edgeLabel(kind, group.find((e) => e.label)?.label),
      sourceHandle: vertical ? 'sb' : 'sr',
      targetHandle: enter,
    })
  }

  return { nodes: junctions, edges }
}

/**
 * Only file edges keep their annotation, and only the verbs that say something:
 * every file is OPENed and CLOSEd, so "OPEN,WRITE,CLOSE" is just "WRITE" with
 * three times the width to overlap its neighbours. A copybook's mechanism is
 * already its node sublabel, so repeating "EXEC SQL INCLUDE" on each of eight
 * edges only stacks text over the fan-in.
 */
function edgeLabel(kind: RepoEdgeKind, label?: string): string | undefined {
  if (kind !== 'file' || !label) return undefined
  const verbs = label.split(',').filter((v) => v !== 'OPEN' && v !== 'CLOSE')
  return verbs.length ? verbs.join(',') : label
}

function edgeKind(kind: RepoEdgeKind): GraphEdge['kind'] {
  if (kind === 'call') return 'performs'
  if (kind === 'copy') return 'copy'
  if (kind === 'sql') return 'sql'
  return 'file'
}

/**
 * Depth of each repo program in the CALL graph — 0 for anything nothing else
 * calls. Iterative with a pass cap so a cyclic CALL chain (COBOL allows it)
 * cannot hang the layout.
 */
function callDepths(payload: RepoGraphPayload): Map<string, number> {
  const calls = payload.edges.filter((e) => e.kind === 'call')
  const depth = new Map<string, number>(payload.nodes.map((n) => [n.id, 0]))
  for (let pass = 0; pass < payload.nodes.length; pass += 1) {
    let changed = false
    for (const e of calls) {
      const next = (depth.get(e.from) ?? 0) + 1
      if (next > (depth.get(e.to) ?? 0)) {
        depth.set(e.to, next)
        changed = true
      }
    }
    if (!changed) break
  }
  return depth
}
