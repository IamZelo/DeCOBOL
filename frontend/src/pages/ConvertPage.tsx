import { useNavigate } from 'react-router-dom'
import { TopNav } from '../components/TopNav'
import { useConversion } from '../hooks/useConversion'
import { useWorkspace } from '../hooks/useWorkspace'
import { formatBytes } from '../lib/format'
import type { PrecisionMode } from '../hooks/useConversion'

function Radio({ on }: { on: boolean }) {
  return <span className={on ? 'radio is-on' : 'radio'} aria-hidden="true" />
}

const PRECISIONS: { id: PrecisionMode; title: string; note: string }[] = [
  {
    id: 'big_decimal',
    title: 'Strict BigDecimal (DECIMAL128)',
    note: 'Zero precision loss. Mainframe truncate and half-adjust rules.',
  },
]

export function ConvertPage() {
  const navigate = useNavigate()
  const { selected, findNode, root } = useWorkspace()
  const {
    javaPackage,
    precision,
    confirmLocal,
    submitting,
    submitError,
    setJavaPackage,
    setPrecision,
    setConfirmLocal,
    startConversion,
  } = useConversion()

  const selectedNodes = selected.map((path) => findNode(path)).filter(Boolean)
  const totalBytes = selectedNodes.reduce((n, node) => n + (node?.size ?? 0), 0)

  async function onStart() {
    await startConversion(selected)
    navigate('/pipeline')
  }

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span className="dot" />
            <span>{root ?? 'Air-gapped daemon :8080'}</span>
          </>
        }
      />

      <div className="page">
        <div className="page-inner">
          <div className="page-lead">
            <h1 className="h1">Convert Batch</h1>
            <p>
              Review selected COBOL source files and confirm Java synthesis
              parameters.
            </p>
          </div>

          <div className="convert-grid">
            <section className="panel convert-card">
              <header className="convert-card-head">
                <span className="label">
                  Selected sources ({selected.length})
                </span>
                <span className="meta">{formatBytes(totalBytes)}</span>
              </header>

              <div className="convert-manifest">
                {selected.length === 0 ? (
                  <p className="meta">
                    No files selected. Go back to Workspace and pick some.
                  </p>
                ) : (
                  selected.map((path) => {
                    const node = findNode(path)
                    return (
                      <div className="convert-source" key={path}>
                        <div className="convert-source-row">
                          <b>{path}</b>
                          <span className="meta">
                            {node?.size != null ? formatBytes(node.size) : ''}
                          </span>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>

              <footer className="convert-card-foot">
                <span className="meta">Output directory</span>
                <span className="convert-outdir">OUTPUT_ROOT</span>
              </footer>
            </section>

            <section className="panel convert-card convert-options">
              <header className="convert-card-head">
                <span className="label">Conversion options</span>
              </header>

              <div className="field">
                <label className="label" htmlFor="pkg">
                  Target package name
                </label>
                <input
                  id="pkg"
                  className="text-input"
                  value={javaPackage}
                  onChange={(e) => setJavaPackage(e.target.value)}
                />
              </div>

              <div className="field">
                <span className="label">Target runtime</span>
                <div className="field-fact">
                  <b>Java 21 LTS</b>
                  <span className="meta">
                    Virtual Threads &amp; Records — the only runtime this build
                    verifies against.
                  </span>
                </div>
              </div>

              <div className="field">
                <span className="label">Financial precision</span>
                <div className="choice-stack">
                  {PRECISIONS.map((opt) => (
                    <button
                      key={opt.id}
                      className={
                        precision === opt.id
                          ? 'choice is-selected is-wide'
                          : 'choice is-wide'
                      }
                      onClick={() => setPrecision(opt.id)}
                    >
                      <Radio on={precision === opt.id} />
                      <span className="choice-body">
                        <b>{opt.title}</b>
                        <span className="meta">{opt.note}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="convert-submit">
                <button
                  className="confirm"
                  onClick={() => setConfirmLocal(!confirmLocal)}
                >
                  <span className={confirmLocal ? 'tick is-on' : 'tick'}>
                    {confirmLocal ? (
                      <svg viewBox="0 0 12 12" width="12" height="12">
                        <path
                          d="M2.5 6.2 4.8 8.5 9.5 3.8"
                          fill="none"
                          stroke="var(--bg)"
                          strokeWidth="1.8"
                          strokeLinecap="square"
                        />
                      </svg>
                    ) : null}
                  </span>
                  <span className="meta">
                    Confirm air-gapped local execution on socket{' '}
                    <span className="confirm-socket">localhost:8080</span>
                  </span>
                </button>

                {submitError ? (
                  <p className="form-error">{submitError}</p>
                ) : null}

                <div className="convert-buttons">
                  <button
                    className="btn-primary"
                    disabled={!confirmLocal || submitting || selected.length === 0}
                    onClick={onStart}
                  >
                    {submitting ? 'Starting…' : 'Start Conversion Pipeline'}
                    <span className="btn-key">↵</span>
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
