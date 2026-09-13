import { useEffect, useMemo, useState } from 'react'
import { getJob } from '../api/client'
import { ExecutionLog, type LogLine } from '../components/ExecutionLog'
import { TopNav } from '../components/TopNav'
import { WorkflowGraph, type StepState } from '../components/WorkflowGraph'
import { PIPELINE_BATCH, PIPELINE_STEPS, TELEMETRY_SEED } from '../data/fixtures'
import { useConversion } from '../hooks/useConversion'
import { useJobEvents } from '../hooks/useJobEvents'
import { formatClock } from '../lib/format'
import type { Job } from '../types'

const SEED_STATES: Record<string, StepState> = {
  PARSER: 'done',
  CONVERTER: 'done',
  OPTIMIZER: 'done',
  VALIDATOR: 'active',
  DOCUMENTER: 'pending',
}

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed'])

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

export function PipelinePage() {
  const { jobId, batchJobs, setActiveJobId } = useConversion()
  const selectedJobId = jobId
  const { events } = useJobEvents(selectedJobId)
  const [wrap, setWrap] = useState(false)
  const [autoscroll, setAutoscroll] = useState(true)
  const [jobsById, setJobsById] = useState<Record<string, Job>>({})

  const knownSelectedJob = selectedJobId ? jobsById[selectedJobId] : undefined
  const knownSourcePath = knownSelectedJob?.source_path ?? knownSelectedJob?.filename
  const knownFilename = knownSelectedJob?.filename

  const trackedJobs = useMemo(() => {
    if (batchJobs.length) return batchJobs
    if (!selectedJobId) return []
    return [
      {
        job_id: selectedJobId,
        source_path: knownSourcePath ?? 'current-job',
        filename: knownFilename ?? 'current-job',
      },
    ]
  }, [batchJobs, knownFilename, knownSourcePath, selectedJobId])

  const selectedJob = knownSelectedJob ?? null
  const hasLiveJob = Boolean(selectedJobId)

  // Poll all submitted files for the explorer and aggregate codebase status.
  // The selected file's detailed stream still comes from SSE below.
  useEffect(() => {
    const ids = trackedJobs.map((j) => j.job_id)
    if (!ids.length) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const jobs = await Promise.all(ids.map((id) => getJob(id)))
        if (cancelled) return
        setJobsById((prev) => {
          const next = { ...prev }
          for (const j of jobs) next[j.job_id] = j
          return next
        })
        if (jobs.some((j) => !TERMINAL.has(j.status))) timer = setTimeout(poll, 1500)
      } catch {
        if (!cancelled) timer = setTimeout(poll, 2500)
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [trackedJobs])

  const batchStats = useMemo(() => {
    const total = trackedJobs.length
    const jobs = trackedJobs.map((j) => jobsById[j.job_id])
    const completed = jobs.filter((j) => j && j.status === 'completed').length
    const warned = jobs.filter((j) => j && j.status === 'completed_with_warnings').length
    const failed = jobs.filter((j) => j && j.status === 'failed').length
    const running = jobs.filter((j) => j && j.status === 'running').length
    const queued = total - completed - warned - failed - running
    const terminal = total > 0 && completed + warned + failed === total
    const label =
      total === 0
        ? 'No active codebase run'
        : terminal
          ? failed
            ? `Codebase failed: ${failed}/${total} files`
            : warned
              ? `Codebase completed with warnings: ${completed + warned}/${total}`
              : `Codebase verified: ${completed}/${total}`
          : `Codebase running: ${completed + warned + failed}/${total} files done`
    return { total, completed, warned, failed, running, queued, terminal, label }
  }, [jobsById, trackedJobs])

  const lines: LogLine[] = useMemo(() => {
    if (!hasLiveJob) return TELEMETRY_SEED.map((l) => ({ ...l }) as LogLine)
    if (!events.length) {
      return [
        {
          ts: formatClock(Date.now() / 1000),
          text: selectedJobId ? 'Waiting for telemetry stream...' : 'Select a file to view telemetry.',
          tone: 'dim',
        },
      ]
    }
    return events.map((e) => ({
      ts: formatClock(e.ts),
      text: e.message,
      tone:
        e.type === 'error'
          ? 'accent'
          : e.type === 'retry_scheduled' || e.type === 'decision'
            ? 'accent'
            : 'dim',
    }))
  }, [events, hasLiveJob, selectedJobId])

  const states: Record<string, StepState> = useMemo(() => {
    if (!hasLiveJob) return SEED_STATES
    const next: Record<string, StepState> = {}
    for (const step of PIPELINE_STEPS) next[step.agent] = 'pending'
    for (const e of events) {
      if (!e.agent) continue
      const key = e.agent.toUpperCase()
      if (!(key in next)) continue
      if (e.type === 'agent_started') next[key] = 'active'
      if (e.type === 'agent_finished') next[key] = 'done'
    }
    if (!events.length && selectedJob?.status === 'queued') next.PARSER = 'pending'
    return next
  }, [events, hasLiveJob, selectedJob?.status])

  const retry = useMemo(() => {
    if (!hasLiveJob) return PIPELINE_BATCH.retry_note
    const last = [...events]
      .reverse()
      .find((e) => e.type === 'retry_scheduled' || e.type === 'decision')
    return last?.message ?? null
  }, [events, hasLiveJob])

  const retryLabel = hasLiveJob
    ? (() => {
        const r = [...events].reverse().find((e) => e.type === 'retry_scheduled')
        const count = (r?.data as { retry_count?: number })?.retry_count
        const max = (r?.data as { max_retries?: number })?.max_retries
        return count != null ? `↳ retry cycle ${count}/${max ?? 3}:` : null
      })()
    : PIPELINE_BATCH.retry_cycle

  const source = hasLiveJob ? selectedJob?.source_path ?? selectedJob?.filename ?? '…' : PIPELINE_BATCH.source
  const target = hasLiveJob
    ? selectedJob?.result?.class_name
      ? `${selectedJob.result.class_name}.java`
      : '…'
    : PIPELINE_BATCH.target
  const fileStatusLabel = hasLiveJob ? statusLabel(selectedJob?.status ?? 'queued') : 'ACTIVE'

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span className={batchStats.failed ? 'dot' : batchStats.terminal ? 'dot is-live' : 'dot'} />
            <span>{batchStats.label}</span>
            <span>JVM 21 TARGET</span>
          </>
        }
      />

      <div className="pipeline-workspace">
        <aside className="explorer pipeline-explorer">
          <div className="explorer-search">
            <span className="label">Codebase Pipeline</span>
            <div className="pipeline-summary">
              <b>{batchStats.total || 1} files</b>
              <span className="meta">
                {batchStats.completed} verified · {batchStats.warned} warnings · {batchStats.failed} failed · {batchStats.running + batchStats.queued} active
              </span>
            </div>
          </div>

          <div className="explorer-tree">
            {trackedJobs.length ? (
              trackedJobs.map((entry) => {
                const job = jobsById[entry.job_id]
                const active = entry.job_id === selectedJobId
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
                    <span className={`pipeline-status ${statusTone(job?.status)}`}>
                      {statusLabel(job?.status)}
                    </span>
                  </button>
                )
              })
            ) : (
              <p className="meta explorer-status">
                Start a conversion from Workspace to track every selected file here.
              </p>
            )}
          </div>
        </aside>

        <main className="pipeline-main">
          <section className="pipeline-active">
            <div className="pipeline-filebar">
              <h2 className="pipeline-title">
                <b>{source}</b>
                <span className="pipeline-arrow">→</span>
                <b>{target}</b>
              </h2>
              <div className="pipeline-filemeta">
                {!hasLiveJob ? (
                  <>
                    <span>{PIPELINE_BATCH.loc}</span>
                    <span>{PIPELINE_BATCH.dialect}</span>
                  </>
                ) : null}
                <span className="is-accent">{fileStatusLabel}</span>
              </div>
            </div>

            <WorkflowGraph states={states} />

            {retry && retryLabel ? (
              <p className="pipeline-retry">
                <span className="is-accent">{retryLabel}</span>
                <span>{retry}</span>
              </p>
            ) : null}
          </section>

          <section className="pipeline-log">
            <header className="pipeline-log-head">
              <span className="meta">Telemetry stream</span>
              <div className="pipeline-log-controls">
                <button className="bracket" onClick={() => setWrap(!wrap)}>
                  [WRAP]
                </button>
                <button
                  className="bracket"
                  onClick={() => setAutoscroll(!autoscroll)}
                >
                  AUTOSCROLL {autoscroll ? 'ON' : 'OFF'}
                </button>
              </div>
            </header>
            <ExecutionLog lines={lines} wrap={wrap} autoscroll={autoscroll} />
          </section>
        </main>
      </div>
    </div>
  )
}
