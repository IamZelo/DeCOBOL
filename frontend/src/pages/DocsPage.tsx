import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getWorkspaceDocs } from '../api/client'
import { IconFile, IconLayers } from '../components/icons'
import { TopNav } from '../components/TopNav'
import { useConversion } from '../hooks/useConversion'
import { formatTimestamp } from '../lib/format'
import type { DocumentedProgram, RepoEdgeKind, WorkspaceDocs } from '../types'

/** How each dependency kind reads in a per-program sentence. */
const EDGE_LABEL: Record<RepoEdgeKind, string> = {
  call: 'Calls',
  copy: 'Includes',
  sql: 'DB2 tables',
  file: 'Datasets',
}

type View = 'rendered' | 'markdown'

function javadocProse(javadoc: string | null): string {
  if (!javadoc) return ''
  return javadoc
    .replace('/**', '')
    .replace('*/', '')
    .split('\n')
    .map((line) => line.trim().replace(/^\*+\s?/, '').trim())
    .filter((line) => line && !line.startsWith('@'))
    .join(' ')
}

function anchorFor(program: DocumentedProgram) {
  return `doc-${program.job_id}`
}

interface Dependency {
  kind: RepoEdgeKind
  labels: string[]
}

function ProgramSection({
  program,
  dependencies,
}: {
  program: DocumentedProgram
  dependencies: Dependency[]
}) {
  const counts = program.finding_counts ?? {}
  const summary = javadocProse(program.class_javadoc)
  return (
    <section className="docs-program" id={anchorFor(program)}>
      <div className="docs-program-head">
        <h2 className="h1">
          {program.program_id ?? program.filename}
          <span className="meta"> → {program.class_name}.java</span>
        </h2>
        <div className="docs-program-meta">
          {program.source_path ? <span className="meta">{program.source_path}</span> : null}
          {counts.error ? <span className="badge is-error">{counts.error} error</span> : null}
          {counts.warning ? <span className="badge is-warning">{counts.warning} warning</span> : null}
          {program.used_fallback ? (
            <span className="badge is-warning">fallback skeleton</span>
          ) : null}
        </div>
      </div>

      {summary ? <p className="docs-summary">{summary}</p> : null}

      {dependencies.length > 0 ? (
        <>
          <h3 className="label">Depends on</h3>
          <ul className="docs-list">
            {dependencies.map((d) => (
              <li key={d.kind}>
                {EDGE_LABEL[d.kind]}:{' '}
                {d.labels.map((label, i) => (
                  <span key={label}>
                    {i > 0 ? ', ' : ''}
                    <code>{label}</code>
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {program.methods.length > 0 ? (
        <>
          <h3 className="label">Methods</h3>
          <div className="panel docs-table-wrap">
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Method</th>
                  <th>From COBOL</th>
                  <th>What it does</th>
                </tr>
              </thead>
              <tbody>
                {program.methods.map((m) => (
                  <tr key={m.java_name}>
                    <td>
                      <code>{m.java_name}</code>
                      <span className="meta docs-signature">{m.signature}</span>
                    </td>
                    <td>
                      {m.cobol_paragraph ? <code>{m.cobol_paragraph}</code> : <span className="meta">—</span>}
                    </td>
                    <td>{m.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {program.variable_map.length > 0 ? (
        <>
          <h3 className="label">Field mapping</h3>
          <div className="panel docs-table-wrap">
            <table className="docs-table">
              <thead>
                <tr>
                  <th>COBOL</th>
                  <th>PIC</th>
                  <th>Java</th>
                  <th>Type</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {program.variable_map.map((v, i) => (
                  <tr key={`${v.cobol_name}-${i}`}>
                    <td><code>{v.cobol_name}</code></td>
                    <td><code>{v.pic}</code>{v.usage && v.usage !== 'DISPLAY' ? <span className="meta"> {v.usage}</span> : null}</td>
                    <td><code>{v.java_name}</code></td>
                    <td><code>{v.java_type}</code></td>
                    <td className="meta">{v.note ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {program.migration_notes.length > 0 ? (
        <>
          <h3 className="label">Migration notes</h3>
          <ul className="docs-list">
            {program.migration_notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </>
      ) : null}

      {program.unsupported.length > 0 ? (
        <>
          <h3 className="label">Needs a human</h3>
          <ul className="docs-list">
            {program.unsupported.map((u, i) => (
              <li key={i}>
                <b>{u.feature}</b> <span className="meta">({u.count})</span> — {u.detail}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  )
}

export function DocsPage() {
  const { batchJobs } = useConversion()
  const [docs, setDocs] = useState<WorkspaceDocs | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>('rendered')
  const [copied, setCopied] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getWorkspaceDocs()
      .then((d) => !cancelled && setDocs(d))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [tick])

  const copyMarkdown = useCallback(async () => {
    if (!docs) return
    try {
      await navigator.clipboard.writeText(docs.markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setView('markdown')
    }
  }, [docs])

  // The same scan that draws the workspace graph, sliced per program: what
  // this file calls, includes, reads and writes. Both directions count for
  // datasets — a file read by the program points into it.
  const dependenciesByJob = useMemo(() => {
    const out = new Map<string, Dependency[]>()
    if (!docs?.dependencies) return out
    const labels = new Map(docs.dependencies.nodes.map((n) => [n.id, n.label]))
    for (const program of docs.programs) {
      if (!program.source_path) continue
      const id = `file:${program.source_path}`
      const grouped = new Map<RepoEdgeKind, string[]>()
      for (const edge of docs.dependencies.edges) {
        const other = edge.from === id ? edge.to : edge.to === id ? edge.from : null
        if (!other) continue
        const list = grouped.get(edge.kind) ?? []
        const label = labels.get(other) ?? other
        if (!list.includes(label)) list.push(label)
        grouped.set(edge.kind, list)
      }
      out.set(
        program.job_id,
        (['call', 'copy', 'sql', 'file'] as RepoEdgeKind[])
          .filter((k) => grouped.get(k)?.length)
          .map((kind) => ({ kind, labels: grouped.get(kind) as string[] })),
      )
    }
    return out
  }, [docs])

  // The README covers everything converted so far; say so when the current
  // batch is only part of that, so the extra programs are not a surprise.
  const extraPrograms = useMemo(() => {
    if (!docs || !batchJobs.length) return 0
    const inBatch = new Set(batchJobs.map((j) => j.job_id))
    return docs.programs.filter((p) => !inBatch.has(p.job_id)).length
  }, [docs, batchJobs])

  return (
    <div className="app">
      <TopNav />
      <div className="page is-wide">
        <div className="page-inner is-wide">
          <div className="docs-head">
            <div className="page-lead">
              <h1 className="h1">Conversion Documentation</h1>
              <p>
                A README for the converted workspace: what each generated method does, which
                COBOL paragraph it came from, how the fields map, and what still needs a human.
              </p>
            </div>
            <div className="docs-actions">
              <div className="analysis-tabs is-sub">
                <button
                  className={view === 'rendered' ? 'analysis-tab is-on' : 'analysis-tab'}
                  onClick={() => setView('rendered')}
                >
                  <IconLayers />
                  Rendered
                </button>
                <button
                  className={view === 'markdown' ? 'analysis-tab is-on' : 'analysis-tab'}
                  onClick={() => setView('markdown')}
                >
                  <IconFile />
                  README.md
                </button>
              </div>
              <button className="btn btn-compact" onClick={copyMarkdown} disabled={!docs}>
                {copied ? 'Copied' : 'Copy README'}
              </button>
              <button className="btn btn-compact" onClick={() => setTick((t) => t + 1)}>
                Refresh
              </button>
            </div>
          </div>

          {error ? (
            <p className="meta is-error">Couldn&rsquo;t load the documentation: {error}</p>
          ) : loading && !docs ? (
            <p className="meta">Assembling documentation from every completed job&hellip;</p>
          ) : docs && docs.program_count === 0 ? (
            <p className="meta">
              Nothing converted yet. Run a conversion from{' '}
              <Link to="/workspace" className="path-accent">
                Workspace
              </Link>{' '}
              and the README will be generated from it.
            </p>
          ) : docs ? (
            <>
              <div className="docs-stats">
                <span>
                  <b>{docs.program_count}</b> program{docs.program_count === 1 ? '' : 's'} converted
                </span>
                <span>
                  <b>{docs.method_count}</b> method{docs.method_count === 1 ? '' : 's'} documented
                </span>
                <span>
                  <b>{docs.field_count}</b> field{docs.field_count === 1 ? '' : 's'} mapped
                </span>
                <span className="meta">Generated {formatTimestamp(docs.generated_ts)}</span>
              </div>

              {extraPrograms > 0 ? (
                <p className="meta docs-scope-note">
                  Includes {extraPrograms} program{extraPrograms === 1 ? '' : 's'} converted
                  outside the current batch.
                </p>
              ) : null}

              {view === 'markdown' ? (
                <pre className="panel docs-markdown">{docs.markdown}</pre>
              ) : (
                <>
                  <nav className="docs-toc">
                    {docs.programs.map((p) => (
                      <a className="docs-toc-link" key={p.job_id} href={`#${anchorFor(p)}`}>
                        {p.program_id ?? p.filename}
                      </a>
                    ))}
                  </nav>
                  {docs.programs.map((p) => (
                    <ProgramSection
                      key={p.job_id}
                      program={p}
                      dependencies={dependenciesByJob.get(p.job_id) ?? []}
                    />
                  ))}
                </>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
