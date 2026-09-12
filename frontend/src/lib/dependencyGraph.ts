import type { ParsedAst } from '../types'

export type GraphNodeKind = 'program' | 'paragraph' | 'copybook' | 'file' | 'table'

export interface GraphNode {
  id: string
  kind: GraphNodeKind
  label: string
  sublabel?: string
  x: number
  y: number
  w: number
  h: number
}

export interface GraphEdge {
  from: string
  to: string
  kind: 'contains' | 'performs' | 'copy' | 'file' | 'sql'
}

export interface DependencyGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width: number
  height: number
}

const ROW_H = 34
const NODE_H = 24
const COL_PROGRAM_X = 16
const COL_PARAGRAPH_X = 280
const COL_EXTERNAL_X = 640
const PROGRAM_W = 220
const PARAGRAPH_W = 300
const EXTERNAL_W = 260

/**
 * Lays out the COBOL program's own structure as a graph: the program at the
 * root, its paragraphs (from paragraphs[].performs — the local call graph),
 * and the external dependencies each paragraph or the program itself touches
 * (COPY/EXEC SQL INCLUDE copybooks, file I/O, SQL tables). Built entirely
 * from CONTRACTS §3 fields the backend already returns per job — no new
 * backend surface needed.
 */
export function buildDependencyGraph(ast: ParsedAst): DependencyGraph {
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []

  const programId = `program:${ast.program_id}`
  nodes.push({
    id: programId,
    kind: 'program',
    label: ast.program_id,
    sublabel: 'PROGRAM-ID',
    x: COL_PROGRAM_X,
    y: 8,
    w: PROGRAM_W,
    h: NODE_H,
  })

  const paragraphs = ast.paragraphs ?? []
  const paragraphIds = new Map<string, string>()
  paragraphs.forEach((p, i) => {
    const id = `para:${p.name}`
    paragraphIds.set(p.name, id)
    nodes.push({
      id,
      kind: 'paragraph',
      label: p.name,
      sublabel: p.section ?? undefined,
      x: COL_PARAGRAPH_X,
      y: 8 + i * ROW_H,
      w: PARAGRAPH_W,
      h: NODE_H,
    })
  })

  // Program contains every paragraph that nothing else PERFORMs (entry
  // points) — draw those from the program node; the rest are reached only
  // via PERFORM, which is the more informative edge to show.
  const performed = new Set(paragraphs.flatMap((p) => p.performs ?? []))
  for (const p of paragraphs) {
    if (!performed.has(p.name)) {
      edges.push({ from: programId, to: paragraphIds.get(p.name)!, kind: 'contains' })
    }
  }
  for (const p of paragraphs) {
    for (const target of p.performs ?? []) {
      const targetId = paragraphIds.get(target)
      if (targetId) edges.push({ from: paragraphIds.get(p.name)!, to: targetId, kind: 'performs' })
    }
  }

  // External dependencies, stacked in their own column.
  let externalRow = 0
  const externalIds = new Map<string, string>()

  for (const cb of ast.copybooks ?? []) {
    const id = `copy:${cb.name}`
    externalIds.set(`copy:${cb.name}`, id)
    nodes.push({
      id,
      kind: 'copybook',
      label: cb.name,
      sublabel: cb.mechanism === 'COPY' ? 'COPY' : 'EXEC SQL INCLUDE',
      x: COL_EXTERNAL_X,
      y: 8 + externalRow * ROW_H,
      w: EXTERNAL_W,
      h: NODE_H,
    })
    edges.push({ from: programId, to: id, kind: 'copy' })
    externalRow += 1
  }

  for (const file of ast.files ?? []) {
    const id = `file:${file.cobol_name}`
    externalIds.set(`file:${file.cobol_name}`, id)
    nodes.push({
      id,
      kind: 'file',
      label: file.cobol_name,
      sublabel: file.assign_to ? `ASSIGN ${file.assign_to}` : undefined,
      x: COL_EXTERNAL_X,
      y: 8 + externalRow * ROW_H,
      w: EXTERNAL_W,
      h: NODE_H,
    })
    edges.push({ from: programId, to: id, kind: 'file' })
    externalRow += 1
  }

  const seenTables = new Set<string>()
  for (const block of ast.sql_blocks ?? []) {
    for (const table of block.tables ?? []) {
      const key = `table:${table}`
      if (!seenTables.has(key)) {
        seenTables.add(key)
        const id = key
        externalIds.set(key, id)
        nodes.push({
          id,
          kind: 'table',
          label: table,
          sublabel: 'SQL TABLE',
          x: COL_EXTERNAL_X,
          y: 8 + externalRow * ROW_H,
          w: EXTERNAL_W,
          h: NODE_H,
        })
        externalRow += 1
      }
      const fromId = block.paragraph ? paragraphIds.get(block.paragraph) : undefined
      edges.push({ from: fromId ?? programId, to: key, kind: 'sql' })
    }
  }

  const height =
    Math.max(8 + paragraphs.length * ROW_H, 8 + externalRow * ROW_H, 60) + NODE_H
  const width = COL_EXTERNAL_X + EXTERNAL_W + 16

  return { nodes, edges, width, height }
}
