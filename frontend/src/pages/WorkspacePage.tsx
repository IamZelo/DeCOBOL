import { useNavigate } from 'react-router-dom'
import { CodeEditor } from '../components/CodeEditor'
import { TopNav } from '../components/TopNav'
import { UploadPanel } from '../components/UploadPanel'
import { useWorkspace } from '../hooks/useWorkspace'
import { formatBytes } from '../lib/format'

export function WorkspacePage() {
  const navigate = useNavigate()
  const { selected, activePath, activeContent, activeLoading, activeError, root } =
    useWorkspace()

  const activeName = activePath?.split('/').pop() ?? ''
  const selectedBytes = 0 // sizes aren't fetched for unread files; shown per-row instead

  return (
    <div className="app">
      <TopNav
        right={
          <>
            <span className="dot is-live" />
            <span>{root ?? '/workspace/input'}</span>
          </>
        }
      />

      <div className="workspace">
        <UploadPanel />

        <main className="workspace-main">
          {activePath ? (
            <>
              <div className="workspace-filebar">
                <div className="workspace-filebar-id">
                  <h2>{activeName}</h2>
                  <span className="meta">{activePath}</span>
                </div>
                <div className="workspace-filebar-meta">
                  {activeContent != null ? (
                    <span>{formatBytes(new Blob([activeContent]).size)}</span>
                  ) : null}
                </div>
              </div>

              <div className="workspace-viewer">
                {activeLoading ? <p className="meta">Loading…</p> : null}
                {activeError ? <p className="meta is-error">{activeError}</p> : null}
                {activeContent != null && !activeLoading ? (
                  <CodeEditor code={activeContent} />
                ) : null}
              </div>
            </>
          ) : (
            <div className="workspace-empty">
              <p className="meta">Select a file from the tree to preview it.</p>
            </div>
          )}
        </main>
      </div>

      <footer className="workspace-actions">
        <span className="meta">
          {selected.length} files selected
          {selectedBytes ? ` (${formatBytes(selectedBytes)})` : ''}
        </span>
        <div className="workspace-actions-buttons">
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
