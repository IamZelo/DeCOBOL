import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJob } from '../api/client'
import { DependencyGraphView } from '../components/DependencyGraph'
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

export function DiffPage() {
  const { jobId } = useConversion()
  const [tab, setTab] = useState<Tab>('structure')
  const [mode, setMode] = useState<'split' | 'unified'>('split')
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
        if (!TERMINAL.has(j.status)) {
          timer = setTimeout(poll, 1500)
        }
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

  const findings = job?.result?.validation?.findings ?? []
  const ast = job?.result?.parsed_ast
  const graph = useMemo(() => (ast ? buildDependencyGraph(ast) : null), [ast])

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

  const converterResult = job?.agent_results?.find((a) => a.agent === 'converter')
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

  if (!job || !TERMINAL.has(job.status)) {
    return (
      <div className="app">
        <TopNav />
        <div className="page">
          <div className="page-inner">
            <p className="meta">
              Conversion still running —{' '}
              <Link to="/pipeline" className="path-accent">
                watch it on Pipeline
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    )
  }

  const className = job.result?.class_name ?? 'Program'

  return (
    <div className="app">
      <TopNav />

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
    </div>
  )
}
