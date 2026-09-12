import { useNavigate } from 'react-router-dom'
import { CodeEditor } from '../components/CodeEditor'
import { TopNav } from '../components/TopNav'
import { UploadPanel } from '../components/UploadPanel'
import { ACTIVE_FILE_META } from '../data/fixtures'
import { useConversion } from '../hooks/useConversion'
import { formatBytes } from '../lib/format'

export function WorkspacePage() {
  const navigate = useNavigate()
  const { files, selected, activePath, selectedFiles } = useConversion()
  const active = files.find((f) => f.path === activePath) ?? files[0]
  const selectedBytes = selectedFiles.reduce((n, f) => n + f.size_bytes, 0)

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span className="dot is-live" />
            <span>/workspace/input</span>
            <button className="nav-icon" aria-label="Open input directory">
              <svg viewBox="0 0 14 11" width="13" height="10">
                <path
                  d="M.6.6h4.1l1.2 1.5h7.5v8.3H.6z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.1"
                />
              </svg>
            </button>
          </>
        }
      />

      <div className="workspace">
        <UploadPanel />

        <main className="workspace-main">
          <div className="workspace-filebar">
            <div className="workspace-filebar-id">
              <h2>{active.name}</h2>
              <span className="meta">{active.path}</span>
            </div>
            <div className="workspace-filebar-meta">
              <span>{ACTIVE_FILE_META.dialect}</span>
              <span>·</span>
              <span>{ACTIVE_FILE_META.encoding}</span>
              <span>·</span>
              <span>{formatBytes(active.size_bytes)}</span>
            </div>
          </div>

          <div className="workspace-viewer">
            <CodeEditor code={active.cobol_code} />
          </div>

          <div className="workspace-deps">
            <div className="workspace-deps-list">
              <span className="meta">Resolved copybooks:</span>
              {ACTIVE_FILE_META.resolved_copybooks.map((name, i) => (
                <span key={name}>
                  {i > 0 ? <span className="meta">·</span> : null}
                  <span className="workspace-dep">{name}</span>
                </span>
              ))}
            </div>
            <span className="meta">Target: {ACTIVE_FILE_META.target}</span>
          </div>
        </main>
      </div>

      <footer className="workspace-actions">
        <span className="meta">
          {selected.length} files selected ({formatBytes(selectedBytes)})
        </span>
        <div className="workspace-actions-buttons">
          <button className="btn btn-round">Dry run AST</button>
          <button
            className="btn-primary btn-compact"
            disabled={selected.length === 0}
            onClick={() => navigate('/convert')}
          >
            Convert selected ({selected.length} files)
            <span className="btn-key">⌘↵</span>
          </button>
        </div>
      </footer>
    </div>
  )
}
