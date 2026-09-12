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

export function PipelinePage() {
  const { jobId } = useConversion()
  const { events } = useJobEvents(jobId)
  const [wrap, setWrap] = useState(false)
  const [autoscroll, setAutoscroll] = useState(true)
  const [job, setJob] = useState<Job | null>(null)

  const live = events.length > 0

  // Light polling just for header metadata (filename/class name/status) — the
  // step graph and log both come from the live SSE stream above.
  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const j = await getJob(jobId!)
        if (cancelled) return
        setJob(j)
        if (!TERMINAL.has(j.status)) timer = setTimeout(poll, 2000)
      } catch {
        /* header metadata is best-effort */
      }
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [jobId])

  const lines: LogLine[] = useMemo(() => {
    if (!live) return TELEMETRY_SEED.map((l) => ({ ...l }) as LogLine)
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
  }, [events, live])

  const states: Record<string, StepState> = useMemo(() => {
    if (!live) return SEED_STATES
    const next: Record<string, StepState> = {}
    for (const step of PIPELINE_STEPS) next[step.agent] = 'pending'
    for (const e of events) {
      if (!e.agent) continue
      const key = e.agent.toUpperCase()
      if (!(key in next)) continue
      if (e.type === 'agent_started') next[key] = 'active'
      if (e.type === 'agent_finished') next[key] = 'done'
    }
    return next
  }, [events, live])

  const retry = useMemo(() => {
    if (!live) return PIPELINE_BATCH.retry_note
    const last = [...events]
      .reverse()
      .find((e) => e.type === 'retry_scheduled' || e.type === 'decision')
    return last?.message ?? null
  }, [events, live])

  const retryLabel = live
    ? (() => {
        const r = [...events].reverse().find((e) => e.type === 'retry_scheduled')
        const count = (r?.data as { retry_count?: number })?.retry_count
        const max = (r?.data as { max_retries?: number })?.max_retries
        return count != null ? `↳ retry cycle ${count}/${max ?? 3}:` : null
      })()
    : PIPELINE_BATCH.retry_cycle

  const source = live ? job?.filename ?? '…' : PIPELINE_BATCH.source
  const target = live
    ? job?.result?.class_name
      ? `${job.result.class_name}.java`
      : '…'
    : PIPELINE_BATCH.target
  const statusLabel = live ? (job ? job.status.toUpperCase().replace(/_/g, ' ') : 'RUNNING') : 'ACTIVE'

  return (
    <div className="app">
      <TopNav
        right={
          live ? (
            <>
              <span>JOB {jobId?.slice(0, 8)}</span>
              <span>JVM 21 TARGET</span>
            </>
          ) : (
            <>
              <span>{PIPELINE_BATCH.batch}</span>
              <span>JVM 21 TARGET</span>
              <span>DAEMON :8080</span>
            </>
          )
        }
      />

      <div className="page">
        <div className="page-inner">
          <section className="pipeline-active">
            <div className="pipeline-filebar">
              <h2 className="pipeline-title">
                <b>{source}</b>
                <span className="pipeline-arrow">→</span>
                <b>{target}</b>
              </h2>
              <div className="pipeline-filemeta">
                {!live ? (
                  <>
                    <span>{PIPELINE_BATCH.loc}</span>
                    <span>{PIPELINE_BATCH.dialect}</span>
                  </>
                ) : null}
                <span className="is-accent">{statusLabel}</span>
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
        </div>
      </div>
    </div>
  )
}
