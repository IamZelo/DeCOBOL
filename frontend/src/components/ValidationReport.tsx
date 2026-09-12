import type { Finding } from '../types'

function summarise(findings: Finding[], equivalence: string) {
  const counts = { error: 0, warning: 0, info: 0 }
  for (const f of findings) counts[f.severity] += 1
  const parts: string[] = []
  if (counts.error) parts.push(`${counts.error} error${counts.error > 1 ? 's' : ''}`)
  if (counts.warning)
    parts.push(`${counts.warning} warning${counts.warning > 1 ? 's' : ''}`)
  if (counts.info) parts.push(`${counts.info} note${counts.info > 1 ? 's' : ''}`)
  parts.push(equivalence)
  return parts.join(' · ')
}

export function ValidationReport({
  findings,
  equivalence,
}: {
  findings: Finding[]
  equivalence: string
}) {
  return (
    <section className="findings">
      <header className="findings-head">
        <span className="findings-title">Findings</span>
        <span className="meta">{summarise(findings, equivalence)}</span>
      </header>

      <div className="findings-list">
        {findings.map((finding, i) => (
          <article className="finding" key={`${finding.check}-${i}`}>
            <span className={`finding-pip is-${finding.severity}`} />
            <div className="finding-body">
              <div className="finding-title">{finding.message}</div>
              {finding.suggestion ? (
                <p className="meta finding-note">{finding.suggestion}</p>
              ) : null}
            </div>
            <span className="meta finding-check">{finding.check}</span>
          </article>
        ))}
      </div>
    </section>
  )
}
