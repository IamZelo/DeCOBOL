import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJob } from '../api/client'
import { CATEGORY_STYLE, DependencyGraphView } from '../components/DependencyGraph'
import { DiffView } from '../components/DiffView'
import { IconFile, IconGraph, IconSplit, IconStructure } from '../components/icons'
import { StructureView } from '../components/StructureView'
import { TopNav } from '../components/TopNav'
import { ValidationReport } from '../components/ValidationReport'
import { useConversion } from '../hooks/useConversion'
import { buildDependencyGraph } from '../lib/dependencyGraph'
import { buildDiffLines } from '../lib/diff'
import { formatTimestamp } from '../lib/format'
import type { Job } from '../types'

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed'])

const LEGEND: { swatch: string; label: string }[] = [
  { swatch: 'var(--accent)', label: 'PERFORM (call graph)' },
  { swatch: 'var(--accent-yellow)', label: 'COPY / EXEC SQL INCLUDE' },
  { swatch: 'var(--accent-cyan)', label: 'File I/O' },
  { swatch: 'var(--accent-green)', label: 'SQL table' },
]

type Tab = 'structure' | 'code' | 'graph'

const TABS: { id: Tab; label: string; icon: () => JSX.Element }[] = [
  { id: 'structure', label: 'Structure', icon: IconStructure },
  { id: 'code', label: 'Code Split View', icon: IconSplit },
  { id: 'graph', label: 'Dependency Graph', icon: IconGraph },
]

function statusLabel(status: string | undefined) {
  return (status ?? 'queued').toUpperCase().replace(/_/g, ' ')
}

function statusTone(status: string | undefined) {
  if (status === 'completed') return 'is-ok'
  if (status === 'completed_with_warnings') return 'is-warn'
  if (status === 'failed') return 'is-error'
  if (status === 'running') return 'is-live'
  return ''
}

export function DiffPage() {
  const { jobId, batchJobs, setActiveJobId } = useConversion()
  const [tab, setTab] = useState<Tab>('structure')
  const [mode, setMode] = useState<'split' | 'unified'>('split')
  const [jobsById, setJobsById] = useState<Record<string, Job>>({})
  const [error, setError] = useState<string | null>(null)

  const knownSelectedJob = jobId ? jobsById[jobId] : undefined
  const knownSourcePath = knownSelectedJob?.source_path ?? knownSelectedJob?.filename
  const knownFilename = knownSelectedJob?.filename

  const trackedJobs = useMemo(() => {
    if (batchJobs.length && batchJobs.some((j) => j.job_id === jobId)) {
      return batchJobs
    }
    if (!jobId) return []
    return [
      {
        job_id: jobId,
        source_path: knownSourcePath ?? 'current-job',
        filename: knownFilename ?? 'current-job',
      },
    ]
  }, [batchJobs, jobId, knownFilename, knownSourcePath])

  useEffect(() => {
    const ids = trackedJobs.map((j) => j.job_id)
    if (!ids.length) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const jobs = await Promise.all(ids.map((id) => getJob(id)))
        if (cancelled) return
        setError(null)
        setJobsById((prev) => {
          const next = { ...prev }
          for (const j of jobs) next[j.job_id] = j
          return next
        })
        if (jobs.some((j) => !TERMINAL.has(j.status))) timer = setTimeout(poll, 1500)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
          timer = setTimeout(poll, 2500)
        }
      }
    }
    poll()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [trackedJobs])

  const job = knownSelectedJob ?? null

  const findings = job?.result?.validation?.findings ?? []
  const ast = job?.result?.parsed_ast
  const converterResult = job?.agent_results?.find((a) => a.agent === 'converter')
  const agentRefactored = converterResult ? !converterResult.used_fallback : false
  const graph = useMemo(
    () => (ast ? buildDependencyGraph(ast, agentRefactored) : null),
    [ast, agentRefactored],
  )

  const sourceLines = useMemo(
    () => (job?.raw_cobol ? buildDiffLines(job.raw_cobol, findings, 'cobol') : []),
    [job?.raw_cobol, findings],
  )
  const targetLines = useMemo(
    () => (job?.result?.java_code ? buildDiffLines(job.result.java_code, findings, 'java') : []),
    [job?.result?.java_code, findings],
  )

  const equivalence = job?.result?.validation
    ? job.result.validation.passed
      ? '100% equivalence'
      : 'equivalence not verified'
    : ''

  const javaBadge = converterResult?.used_fallback
    ? { label: 'FALLBACK SKELETON', tone: 'warning' as const }
    : converterResult?.confidence != null
      ? { label: `Confidence: ${Math.round(converterResult.confidence * 100)}%`, tone: 'success' as const }
      : undefined

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
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    )
  }

  const explorer = (
    <aside className="explorer pipeline-explorer">
      <div className="explorer-search">
        <span className="label">Codebase Analysis</span>
        <div className="pipeline-summary">
          <b>{trackedJobs.length || 1} files</b>
          <span className="meta">Select a file to inspect its structure, code, and graph.</span>
        </div>
      </div>

      <div className="explorer-tree">
        {trackedJobs.map((entry) => {
          const item = jobsById[entry.job_id]
          const active = entry.job_id === jobId
          const parts = entry.source_path.split('/')
          const dirname = parts.length > 1 ? parts.slice(0, -1).join('/') : 'input'
          return (
            <button
              key={entry.job_id}
              className={active ? 'pipeline-file-row is-active' : 'pipeline-file-row'}
              onClick={() => setActiveJobId(entry.job_id)}
            >
              <span className="pipeline-file-path">
                <span className="meta">{dirname}/</span>
                <b>{entry.filename}</b>
              </span>
              <span className={`pipeline-status ${statusTone(item?.status)}`}>
                {statusLabel(item?.status)}
              </span>
            </button>
          )
        })}
      </div>
    </aside>
  )

  if (error || !job || !TERMINAL.has(job.status)) {
    return (
      <div className="app">
        <TopNav />
        <div className="analysis-workspace">
          {explorer}
          <main className="analysis-main">
            <div className="page is-wide">
              <div className="page-inner is-wide">
                {error ? <p className="meta is-error">{error}</p> : null}
                {!error ? (
                  <p className="meta">
                    {job ? 'Conversion still running' : 'Loading analysis'} —{' '}
                    <Link to="/pipeline" className="path-accent">
                      watch it on Pipeline
                    </Link>
                    .
                  </p>
                ) : null}
              </div>
            </div>
          </main>
        </div>
      </div>
    )
  }

  const className = job.result?.class_name ?? 'Program'

  return (
    <div className="app">
      <TopNav />

      <div className="analysis-workspace">
        {explorer}

        <main className="analysis-main">
          <div className="analysis-topbar">
            <div className="analysis-breadcrumb">
              <IconFile />
              <Link to="/workspace" className="meta">
                {job.source_path ? job.source_path.split('/').slice(0, -1).join('/') || 'src' : 'src'}
              </Link>
              <span className="meta">/</span>
              <b>{job.filename ?? 'source.cbl'}</b>
            </div>
            <div className="analysis-status">
              <span className={job.result?.validation?.passed === false ? 'dot' : 'dot is-live'} />
              <span className="meta">
                {job.status === 'completed_with_warnings' ? 'Completed with warnings' : job.status.replace(/_/g, ' ')}
              </span>
              <Link to="/convert" className="btn-primary btn-compact">
                Run Conversion
              </Link>
            </div>
          </div>

          <div className="page is-wide">
            <div className="page-inner is-wide">
          <div className="page-lead">
            <h1 className="h1">{job.filename ?? 'Program'} Analysis</h1>
            <p>
              Multi-agent conversion pipeline overview for {job.result?.parsed_ast?.program_id ?? className}.
              Review the field/method structure, the raw code side by side, and its call graph below.
            </p>
          </div>

          <div className="analysis-tabs">
            {TABS.map((t) => {
              const Icon = t.icon
              return (
                <button
                  key={t.id}
                  className={tab === t.id ? 'analysis-tab is-on' : 'analysis-tab'}
                  onClick={() => setTab(t.id)}
                >
                  <Icon />
                  {t.label}
                </button>
              )
            })}
          </div>

          {tab === 'structure' ? <StructureView job={job} findings={findings} /> : null}

          {tab === 'code' ? (
            <>
              <div className="diff-toolbar">
                <div className="segmented">
                  <button
                    className={mode === 'split' ? 'is-on' : ''}
                    onClick={() => setMode('split')}
                  >
                    SPLIT
                  </button>
                  <button
                    className={mode === 'unified' ? 'is-on' : ''}
                    onClick={() => setMode('unified')}
                  >
                    UNIFIED
                  </button>
                </div>
              </div>
              <DiffView
                mode={mode}
                source={{
                  name: 'Original COBOL',
                  meta: job.filename ?? 'source.cbl',
                  lines: sourceLines.length,
                  rows: sourceLines,
                  badge: { label: 'Read-only', tone: 'neutral' },
                }}
                target={{
                  name: 'Converted Java',
                  meta: `${className}.java`,
                  lines: targetLines.length,
                  rows: targetLines,
                  badge: javaBadge,
                }}
              />
            </>
          ) : null}

          {tab === 'graph' ? (
            graph ? (
              <>
                <div className="depgraph-legend">
                  {(Object.keys(CATEGORY_STYLE) as (keyof typeof CATEGORY_STYLE)[]).map((key) => (
                    <span className="depgraph-legend-item" key={key}>
                      <span
                        className="depgraph-swatch is-outline"
                        style={{ borderColor: CATEGORY_STYLE[key].stroke }}
                      />
                      {CATEGORY_STYLE[key].label}
                    </span>
                  ))}
                </div>
                <div className="depgraph-legend">
                  {LEGEND.map((item) => (
                    <span className="depgraph-legend-item" key={item.label}>
                      <span className="depgraph-swatch" style={{ background: item.swatch }} />
                      {item.label}
                    </span>
                  ))}
                </div>
                <div className="panel depgraph-panel">
                  <DependencyGraphView graph={graph} />
                </div>
                <div className="depgraph-footer">
                  <span className="meta">
                    Last synced: {job.finished_ts ? formatTimestamp(job.finished_ts) : '—'}
                  </span>
                  <span className="meta">Workspace: {job.source_path ?? '(inline)'}</span>
                </div>
              </>
            ) : (
              <p className="meta">No AST available for this job.</p>
            )
          ) : null}

          {tab !== 'graph' ? <ValidationReport findings={findings} equivalence={equivalence} /> : null}
            </div>
          </div>
        </main>
        </div>
    </div>
  )
}
