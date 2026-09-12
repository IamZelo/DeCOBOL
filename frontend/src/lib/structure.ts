import type { Finding } from '../types'

/**
 * Mirrors the converter's own naming convention (see
 * backend/app/agents/converter_agent.py) so the name shown here is the one
 * the LLM was actually instructed to produce — not a guess.
 */
export function paragraphToMethodName(name: string): string {
  const parts = name
    .split(/[-_]/)
    .filter((p) => p.length > 0 && !/^\d+$/.test(p))
  if (parts.length === 0) return name.toLowerCase()
  const [first, ...rest] = parts
  const head = first.toLowerCase()
  const tail = rest.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
  return [head, ...tail].join('')
}

/** Groups findings by the COBOL symbol (variable or paragraph name) they reference. */
export function findingsByRef(findings: Finding[]): Map<string, Finding[]> {
  const map = new Map<string, Finding[]>()
  for (const f of findings) {
    if (!f.cobol_ref) continue
    const key = f.cobol_ref.toUpperCase()
    const list = map.get(key)
    if (list) list.push(f)
    else map.set(key, [f])
  }
  return map
}

export const SEVERITY_RANK: Record<Finding['severity'], number> = {
  error: 0,
  warning: 1,
  info: 2,
}

export function worstSeverity(findings: Finding[]): Finding['severity'] | null {
  if (findings.length === 0) return null
  return findings.reduce<Finding['severity']>(
    (worst, f) => (SEVERITY_RANK[f.severity] < SEVERITY_RANK[worst] ? f.severity : worst),
    findings[0].severity,
  )
}
