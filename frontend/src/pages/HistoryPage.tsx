import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getJob, listJobs } from '../api/client'
import { TopNav } from '../components/TopNav'
import { useConversion } from '../hooks/useConversion'
import { formatSeconds, formatTimestamp } from '../lib/format'
import type { JobSummary } from '../types'

type Tab = 'all' | 'successful' | 'retried'

interface EnrichedRow extends JobSummary {
  loc: number | null
  passed: boolean | null
}

export function HistoryPage() {
  const navigate = useNavigate()
  const { setActiveJobId } = useConversion()
  const [tab, setTab] = useState<Tab>('all')
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<EnrichedRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const { jobs } = await listJobs()
        if (cancelled) return
        setRows(jobs.map((j) => ({ ...j, loc: null, passed: null })))

        // Job summaries don't carry LOC/pass-rate (CONTRACTS §11) — only the
        // full detail does. Fetch details for terminal jobs to fill those in;
        // fine at this dataset size, would want a summary-field addition to
        // CONTRACTS at real scale.
        const terminal = jobs.filter((j) =>
          ['completed', 'completed_with_warnings', 'failed'].includes(j.status),
        )
        const details = await Promise.all(
          terminal.map((j) => getJob(j.job_id).catch(() => null)),
        )
        if (cancelled) return
        setRows((prev) =>
          prev.map((row) => {
            const detail = details.find((d) => d?.job_id === row.job_id)
            if (!detail) return row
            const loc = detail.result?.java_code
              ? detail.result.java_code.split('\n').length
              : null
            const passed = detail.result?.validation?.passed ?? null
            return { ...row, loc, passed }
          }),
        )
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    let list = rows
    if (tab === 'retried') list = list.filter((r) => r.retry_count > 0)
    if (tab === 'successful') list = list.filter((r) => r.retry_count === 0 && r.status !== 'failed')
    const needle = query.trim().toLowerCase()
    if (needle) {
      list = list.filter(
        (r) =>
          r.job_id.toLowerCase().includes(needle) ||
          (r.source_path ?? '').toLowerCase().includes(needle) ||
          (r.filename ?? '').toLowerCase().includes(needle),
      )
    }
    return list
  }, [rows, tab, query])

  const totals = {
    all: rows.length,
    successful: rows.filter((r) => r.retry_count === 0 && r.status !== 'failed').length,
    retried: rows.filter((r) => r.retry_count > 0).length,
  }

  const totalLoc = rows.reduce((n, r) => n + (r.loc ?? 0), 0)
  const withVerdict = rows.filter((r) => r.passed != null)
  const passRate = withVerdict.length
    ? Math.round((withVerdict.filter((r) => r.passed).length / withVerdict.length) * 100)
    : null

  const tabs: { id: Tab; label: string }[] = [
    { id: 'all', label: `All (${totals.all})` },
    { id: 'successful', label: `Successful (${totals.successful})` },
    { id: 'retried', label: `Retried (${totals.retried})` },
  ]

  function openJob(row: EnrichedRow, route: '/diff' | '/pipeline') {
    const sourcePath = row.source_path ?? row.filename ?? row.job_id
    setActiveJobId(row.job_id, {
      job_id: row.job_id,
      source_path: sourcePath,
      filename: row.filename ?? sourcePath.split('/').pop() ?? row.job_id,
    })
    navigate(route)
  }

  return (
    <div className="app">
      <TopNav right={<span>daemon local</span>} />

      <div className="page">
        <div className="page-inner is-history">
          <header className="history-head">
            <div>
              <h1 className="h1">Audit Log &amp; Run History</h1>
              <p className="meta">Runs served by this backend's in-memory job store.</p>
            </div>
          </header>

          <section className="metrics">
            <div className="metric">
              <span className="label">TOTAL MODERNIZED LOC</span>
              <span className="metric-value">{totalLoc.toLocaleString()}</span>
              <span className="meta">Across {rows.length} runs</span>
            </div>
            <div className="metric">
              <span className="label">VERIFIED PASS RATE</span>
              <span className="metric-value">{passRate != null ? `${passRate}%` : '—'}</span>
              <span className="meta">{withVerdict.length} verified runs</span>
            </div>
            <div className="metric">
              <span className="label">AIR-GAP COMPLIANCE</span>
              <span className="metric-value">Compliant</span>
              <span className="meta">No network egress by design</span>
            </div>
          </section>

          <div className="history-filters">
            <div className="tabs">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  className={tab === t.id ? 'tab is-on' : 'tab'}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <input
              className="text-input is-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search job id or path..."
              aria-label="Search job id or path"
            />
          </div>

          {loading ? <p className="meta">Loading…</p> : null}
          {error ? <p className="meta is-error">{error}</p> : null}

          {!loading && !error ? (
            <div className="table-scroll">
              <table className="audit">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Timestamp</th>
                    <th>Source</th>
                    <th>LOC</th>
                    <th className="is-right">Duration</th>
                    <th>Status</th>
                    <th className="is-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.job_id}>
                      <td className="audit-batch">#{row.job_id.slice(0, 8)}</td>
                      <td className="meta">{formatTimestamp(row.created_ts)}</td>
                      <td className="meta">{row.source_path ?? row.filename ?? '(inline)'}</td>
                      <td>{row.loc ?? '—'}</td>
                      <td className="meta is-right">{formatSeconds(row.duration_ms)}</td>
                      <td>
                        {row.status.replace(/_/g, ' ')}
                        {row.retry_count > 0 ? (
                          <span className="meta audit-retry">
                            {row.retry_count} {row.retry_count === 1 ? 'retry' : 'retries'}
                          </span>
                        ) : null}
                      </td>
                      <td className="is-right">
                        <div className="audit-actions">
                          <button onClick={() => openJob(row, '/diff')}>Diff</button>
                          <button onClick={() => openJob(row, '/pipeline')}>Log</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {!loading && !error && filtered.length === 0 ? (
            <p className="meta">No runs yet — start one from Convert.</p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
