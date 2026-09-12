import type { ParsedAst } from '../types'

export type GraphNodeKind = 'program' | 'paragraph' | 'copybook' | 'file' | 'table'

/**
 * Visual category, independent of `kind`: `agent` marks a paragraph the
 * converter actually sent to the LLM (as opposed to the deterministic Jinja
 * fallback); `external` covers everything the program reaches outside its
 * own procedure division — copybooks, files, SQL tables.
 */
export type GraphNodeCategory = 'standard' | 'agent' | 'external'

export interface GraphNode {
  id: string
  kind: GraphNodeKind
  category: GraphNodeCategory
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

const ROW_H = 64
const NODE_H = 24
const COL_PROGRAM_X = 24
const COL_PARAGRAPH_X = 380
const COL_EXTERNAL_X = 820
const PROGRAM_W = 240
const PARAGRAPH_W = 320
const EXTERNAL_W = 280

/**
 * Lays out the COBOL program's own structure as a graph: the program at the
 * root, its paragraphs (from paragraphs[].performs — the local call graph),
 * and the external dependencies each paragraph or the program itself touches
 * (COPY/EXEC SQL INCLUDE copybooks, file I/O, SQL tables). Built entirely
 * from CONTRACTS §3 fields the backend already returns per job — no new
 * backend surface needed.
 *
 * `agentRefactored` reflects the converter's whole-job `used_fallback` flag
 * (there's no per-paragraph LLM/fallback record yet), so every paragraph in
 * a given job is categorized the same way: `agent` when the LLM actually
 * wrote the Java, `standard` when the deterministic skeleton did.
 */
export function buildDependencyGraph(ast: ParsedAst, agentRefactored = false): DependencyGraph {
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []

  const programId = `program:${ast.program_id}`
  const programNode: GraphNode = {
    id: programId,
    kind: 'program',
    category: 'standard',
    label: ast.program_id,
    sublabel: 'PROGRAM-ID',
    x: COL_PROGRAM_X,
    y: 8,
    w: PROGRAM_W,
    h: NODE_H,
  }
  nodes.push(programNode)

  const paragraphs = ast.paragraphs ?? []
  const paragraphIds = new Map<string, string>()
  paragraphs.forEach((p, i) => {
    const id = `para:${p.name}`
    paragraphIds.set(p.name, id)
    nodes.push({
      id,
      kind: 'paragraph',
      category: agentRefactored ? 'agent' : 'standard',
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
      category: 'external',
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
      category: 'external',
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
          category: 'external',
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

  // Center the program node vertically against whichever column — paragraphs
  // or external dependencies — runs taller, so the fan-out reads as a
  // balanced flowchart root instead of hugging the top edge.
  const totalRows = Math.max(paragraphs.length, externalRow, 1)
  programNode.y = 8 + ((totalRows - 1) * ROW_H) / 2

  const height =
    Math.max(8 + paragraphs.length * ROW_H, 8 + externalRow * ROW_H, 60) + NODE_H
  const width = COL_EXTERNAL_X + EXTERNAL_W + 16

  return { nodes, edges, width, height }
}
