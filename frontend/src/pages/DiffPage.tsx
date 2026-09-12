import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJob } from '../api/client'
import { DiffView } from '../components/DiffView'
import { TopNav } from '../components/TopNav'
import { ValidationReport } from '../components/ValidationReport'
import { useConversion } from '../hooks/useConversion'
import { buildDiffLines } from '../lib/diff'
import type { Job } from '../types'

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed'])

export function DiffPage() {
  const { jobId } = useConversion()
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

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span>Output:</span>
            <span className="path-accent">{job.output_path ?? '(preview only)'}</span>
          </>
        }
      />

      <div className="page is-wide">
        <div className="page-inner is-wide">
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
              name: job.filename ?? 'source.cbl',
              meta: job.result?.parsed_ast?.program_id ?? '',
              lines: sourceLines.length,
              rows: sourceLines,
            }}
            target={{
              name: `${job.result?.class_name ?? 'Program'}.java`,
              meta: 'Java',
              lines: targetLines.length,
              rows: targetLines,
            }}
          />

          <ValidationReport findings={findings} equivalence={equivalence} />
        </div>
      </div>
    </div>
  )
}
