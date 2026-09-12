import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJob } from '../api/client'
import { DependencyGraphView } from '../components/DependencyGraph'
import { TopNav } from '../components/TopNav'
import { useConversion } from '../hooks/useConversion'
import { buildDependencyGraph } from '../lib/dependencyGraph'
import type { Job } from '../types'

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed'])

const LEGEND: { swatch: string; label: string }[] = [
  { swatch: '#d29922', label: 'PERFORM (call graph)' },
  { swatch: '#9c8f7b', label: 'COPY / EXEC SQL INCLUDE' },
  { swatch: '#9296a0', label: 'File I/O' },
  { swatch: '#6d8fb0', label: 'SQL table' },
]

export function GraphPage() {
  const { jobId } = useConversion()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const j = await getJob(jobId!)
        if (cancelled) return
        setJob(j)
        if (!TERMINAL.has(j.status)) timer = setTimeout(poll, 1500)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [jobId])

  const ast = job?.result?.parsed_ast
  const graph = useMemo(() => (ast ? buildDependencyGraph(ast) : null), [ast])

  if (!jobId) {
    return (
      <div className="app">
        <TopNav />
        <div className="page">
          <div className="page-inner">
            <p className="meta">
              No conversion job yet. Start one from{' '}
              <Link to="/convert" className="path-accent">
                Convert
              </Link>{' '}
              to see its structure here.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app">
        <TopNav />
        <div className="page">
          <div className="page-inner">
            <p className="meta is-error">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  if (!job || !TERMINAL.has(job.status) || !graph) {
    return (
      <div className="app">
        <TopNav />
        <div className="page">
          <div className="page-inner">
            <p className="meta">
              Waiting on the parser —{' '}
              <Link to="/pipeline" className="path-accent">
                watch progress on Pipeline
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <TopNav right={<span>{ast?.program_id}</span>} />
      <div className="page is-wide">
        <div className="page-inner is-wide">
          <div className="page-lead">
            <h1 className="h1">Program Structure</h1>
            <p>
              Paragraph call graph, copybooks, file I/O and SQL tables parsed
              from {job.filename}.
            </p>
          </div>

          <div className="depgraph-legend">
            {LEGEND.map((item) => (
              <span className="depgraph-legend-item" key={item.label}>
                <span
                  className="depgraph-swatch"
                  style={{ background: item.swatch }}
                />
                {item.label}
              </span>
            ))}
          </div>

          <div className="panel depgraph-panel">
            <DependencyGraphView graph={graph} />
          </div>
        </div>
      </div>
    </div>
  )
}
