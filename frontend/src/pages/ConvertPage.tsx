import { useNavigate } from 'react-router-dom'
import { TopNav } from '../components/TopNav'
import { useConversion } from '../hooks/useConversion'
import { formatBytes } from '../lib/format'
import type { PrecisionMode, TargetRuntime } from '../hooks/useConversion'

function Radio({ on }: { on: boolean }) {
  return <span className={on ? 'radio is-on' : 'radio'} aria-hidden="true" />
}

const RUNTIMES: { id: TargetRuntime; title: string; note: string }[] = [
  { id: 'java_21', title: 'Java 21 LTS', note: 'Virtual Threads & Records' },
  { id: 'java_17', title: 'Java 17 LTS', note: 'Classic POJOs' },
]

const PRECISIONS: { id: PrecisionMode; title: string; note: string }[] = [
  {
    id: 'big_decimal',
    title: 'Strict BigDecimal (DECIMAL128)',
    note: 'Zero precision loss. Mainframe truncate and half-adjust rules.',
  },
  {
    id: 'native',
    title: 'Native Primitives (double / long)',
    note: 'High throughput. Non-financial workflows only.',
  },
]

export function ConvertPage() {
  const navigate = useNavigate()
  const {
    selectedFiles,
    javaPackage,
    runtime,
    precision,
    confirmLocal,
    submitting,
    submitError,
    setJavaPackage,
    setRuntime,
    setPrecision,
    setConfirmLocal,
    startConversion,
  } = useConversion()

  const totalLines = selectedFiles.reduce((n, f) => n + f.lines, 0)

  async function onStart() {
    await startConversion()
    navigate('/pipeline')
  }

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span className="dot" />
            <span>Air-gapped daemon :8080</span>
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
                  Selected sources ({selectedFiles.length})
                </span>
                <span className="meta">{totalLines} lines</span>
              </header>

              <div className="convert-manifest">
                {selectedFiles.map((file) => (
                  <div className="convert-source" key={file.path}>
                    <div className="convert-source-row">
                      <b>{file.path}</b>
                      <span className="meta">{formatBytes(file.size_bytes)}</span>
                    </div>
                    <span className="meta">
                      {file.lines} lines
                      {file.linkage ? ` · ${file.linkage}` : ''}
                    </span>
                  </div>
                ))}
              </div>

              <footer className="convert-card-foot">
                <span className="meta">Output directory</span>
                <span className="convert-outdir">~/decobol-output/</span>
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
                <div className="choice-row">
                  {RUNTIMES.map((opt) => (
                    <button
                      key={opt.id}
                      className={
                        runtime === opt.id ? 'choice is-selected' : 'choice'
                      }
                      onClick={() => setRuntime(opt.id)}
                    >
                      <span className="choice-head">
                        <Radio on={runtime === opt.id} />
                        <b>{opt.title}</b>
                      </span>
                      <span className="meta">{opt.note}</span>
                    </button>
                  ))}
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
                          stroke="#111318"
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
                    disabled={
                      !confirmLocal || submitting || selectedFiles.length === 0
                    }
                    onClick={onStart}
                  >
                    {submitting ? 'Starting…' : 'Start Conversion Pipeline'}
                    <span className="btn-key">↵</span>
                  </button>
                  <button className="btn">Save Config</button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
