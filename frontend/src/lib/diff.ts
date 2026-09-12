import type { Finding } from '../types'

export type DiffEmphasis = 'none' | 'soft' | 'strong'

export interface DiffLine {
  n: number
  text: string
  emphasis: DiffEmphasis
}

const EMPHASIS_BY_SEVERITY: Record<Finding['severity'], DiffEmphasis> = {
  error: 'strong',
  warning: 'strong',
  info: 'soft',
}

/**
 * Builds emphasis-tagged lines for one side of the diff (COBOL or Java) by
 * matching each finding's cobol_line/java_line against the source's own line
 * numbers. Findings are the only thing the backend gives us that ties a
 * specific line to a specific severity (CONTRACTS §8) — there is no true
 * line-diff algorithm here, just "which lines did the validator flag."
 */
export function buildDiffLines(
  text: string,
  findings: Finding[],
  side: 'cobol' | 'java',
): DiffLine[] {
  const emphasisByLine = new Map<number, DiffEmphasis>()
  for (const finding of findings) {
    const lineNo = side === 'cobol' ? finding.cobol_line : finding.java_line
    if (lineNo == null) continue
    const next = EMPHASIS_BY_SEVERITY[finding.severity]
    const current = emphasisByLine.get(lineNo)
    if (!current || (current === 'soft' && next === 'strong')) {
      emphasisByLine.set(lineNo, next)
    }
  }

  return text.split('\n').map((line, i) => ({
    n: i + 1,
    text: line,
    emphasis: emphasisByLine.get(i + 1) ?? 'none',
  }))
}
