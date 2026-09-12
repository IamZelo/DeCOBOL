import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopNav } from '../components/TopNav'
import {
  AUDIT_LOG_PATH,
  AUDIT_METRICS,
  AUDIT_ROWS,
  AUDIT_TOTALS,
} from '../data/fixtures'

type Tab = 'all' | 'successful' | 'retried'

export function HistoryPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('all')
  const [query, setQuery] = useState('')

  const rows = useMemo(() => {
    let list = AUDIT_ROWS
    if (tab === 'retried') list = list.filter((r) => r.retries)
    if (tab === 'successful') list = list.filter((r) => !r.retries)
    const needle = query.trim().toLowerCase()
    if (needle) {
      list = list.filter(
        (r) =>
          r.batch.toLowerCase().includes(needle) ||
          r.source.toLowerCase().includes(needle),
      )
    }
    return list
  }, [query, tab])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'all', label: `All (${AUDIT_TOTALS.all})` },
    { id: 'successful', label: `Successful (${AUDIT_TOTALS.successful})` },
    { id: 'retried', label: `Retried (${AUDIT_TOTALS.retried})` },
  ]

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span>daemon: :8080</span>
            <span>|</span>
            <span>air-gapped</span>
            <span className="avatar" aria-hidden="true">
              <svg viewBox="0 0 14 14" width="12" height="12">
                <circle
                  cx="7"
                  cy="5"
                  r="2.6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.1"
                />
                <path
                  d="M2.4 12.4a4.9 4.9 0 0 1 9.2 0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.1"
                />
              </svg>
            </span>
          </>
        }
      />

      <div className="page">
        <div className="page-inner is-history">
          <header className="history-head">
            <div>
              <h1 className="h1">Audit Log &amp; Run History</h1>
              <p className="meta">
                Local daemon runs logged under{' '}
                <span className="history-path">{AUDIT_LOG_PATH}</span>
              </p>
            </div>
            <button className="btn">EXPORT CSV</button>
          </header>

          <section className="metrics">
            {AUDIT_METRICS.map((metric) => (
              <div className="metric" key={metric.label}>
                <span className="label">{metric.label}</span>
                <span className="metric-value">{metric.value}</span>
                <span className="meta">{metric.note}</span>
              </div>
            ))}
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
              placeholder="Search batch or path..."
              aria-label="Search batch or path"
            />
          </div>

          <table className="audit">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Timestamp</th>
                <th>Source</th>
                <th>Files</th>
                <th className="is-right">Duration</th>
                <th>Status</th>
                <th className="is-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.batch}>
                  <td className="audit-batch">{row.batch}</td>
                  <td className="meta">{row.timestamp}</td>
                  <td className="meta">{row.source}</td>
                  <td>
                    {row.files} <span className="meta">{row.loc}</span>
                  </td>
                  <td className="meta is-right">{row.duration}</td>
                  <td>
                    {row.status}
                    {row.retries ? (
                      <span className="meta audit-retry">{row.retries}</span>
                    ) : null}
                  </td>
                  <td className="is-right">
                    <div className="audit-actions">
                      <button onClick={() => navigate('/diff')}>Diff</button>
                      <button onClick={() => navigate('/pipeline')}>Log</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <footer className="pager">
            <span className="meta">
              Showing {rows.length} of {AUDIT_TOTALS.all} runs
            </span>
            <div className="pager-controls">
              <button className="is-disabled">Previous</button>
              <span className="is-accent">1</span>
              <button>Next</button>
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}
