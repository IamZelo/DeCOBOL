import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CodeEditor } from '../components/CodeEditor'
import { CATEGORY_STYLE, DependencyGraphView } from '../components/DependencyGraph'
import { IconFile, IconGraph } from '../components/icons'
import { TopNav } from '../components/TopNav'
import { UploadPanel } from '../components/UploadPanel'
import { useRepoGraph } from '../hooks/useRepoGraph'
import { useWorkspace } from '../hooks/useWorkspace'
import { formatBytes } from '../lib/format'
import type { RepoEdgeKind } from '../types'

type View = 'graph' | 'file'

const EDGE_LEGEND: Record<RepoEdgeKind, { swatch: string; label: string }> = {
  call: { swatch: 'var(--accent)', label: 'CALL (program → subprogram)' },
  copy: { swatch: 'var(--accent-yellow)', label: 'COPY / EXEC SQL INCLUDE' },
  file: { swatch: 'var(--accent-cyan)', label: 'File I/O (DD name)' },
  sql: { swatch: 'var(--accent-green)', label: 'DB2 table' },
}

export function WorkspacePage() {
  const navigate = useNavigate()
  const {
    selected,
    activePath,
    activeContent,
    activeLoading,
    activeError,
    root,
    setActivePath,
  } = useWorkspace()
  // The graph loads on mount, from every COBOL file under the input root —
  // not from a conversion job — so it is already populated when the workspace
  // first renders.
  const { graph, loading: graphLoading, error: graphError, reload } = useRepoGraph(activePath)
  const [view, setView] = useState<View>('graph')

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
          <div className="workspace-filebar">
            <div className="workspace-filebar-id">
              <h2>{view === 'graph' ? 'Dependency Graph' : activeName || 'No file selected'}</h2>
              <span className="meta">
                {view === 'graph'
                  ? graph
                    ? `${graph.fileCount} COBOL files · ${graph.edges.length} dependencies`
                    : 'scanning workspace…'
                  : activePath ?? ''}
              </span>
            </div>
            <div className="workspace-filebar-meta">
              {view === 'file' && activeContent != null ? (
                <span>{formatBytes(new Blob([activeContent]).size)}</span>
              ) : null}
              <div className="workspace-view-tabs">
                <button
                  className={view === 'graph' ? 'analysis-tab is-on' : 'analysis-tab'}
                  onClick={() => setView('graph')}
                >
                  <IconGraph />
                  Graph
                </button>
                <button
                  className={view === 'file' ? 'analysis-tab is-on' : 'analysis-tab'}
                  onClick={() => setView('file')}
                >
                  <IconFile />
                  Source
                </button>
              </div>
            </div>
          </div>

          {view === 'graph' ? (
            <div className="workspace-viewer is-graph">
              {graphError ? (
                <p className="meta is-error">
                  Couldn&rsquo;t scan the workspace: {graphError}{' '}
                  <button className="btn btn-compact" onClick={reload}>
                    Retry
                  </button>
                </p>
              ) : graphLoading && !graph ? (
                <p className="meta">Parsing every COBOL file under the input root…</p>
              ) : graph && graph.nodes.length > 0 ? (
                <>
                  <div className="depgraph-legend">
                    {graph.categories.map((key) => (
                      <span className="depgraph-legend-item" key={key}>
                        <span
                          className="depgraph-swatch is-outline"
                          style={{ borderColor: CATEGORY_STYLE[key].stroke }}
                        />
                        {CATEGORY_STYLE[key].label}
                      </span>
                    ))}
                    {graph.edgeKinds.map((kind) => (
                      <span className="depgraph-legend-item" key={kind}>
                        <span
                          className="depgraph-swatch"
                          style={{ background: EDGE_LEGEND[kind].swatch }}
                        />
                        {EDGE_LEGEND[kind].label}
                      </span>
                    ))}
                  </div>
                  <DependencyGraphView
                    graph={graph}
                    onNodeClick={(id) => {
                      const path = graph.pathById.get(id)
                      if (!path) return
                      setActivePath(path)
                      setView('file')
                    }}
                  />
                  {graph.parseErrors.length > 0 ? (
                    <p className="meta workspace-graph-warning">
                      {graph.parseErrors.length} file
                      {graph.parseErrors.length === 1 ? '' : 's'} could not be parsed:{' '}
                      {graph.parseErrors.map((e) => e.path).join(', ')}
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="meta">
                  No COBOL files found under <code>{root}</code>.
                </p>
              )}
            </div>
          ) : activePath ? (
            <div className="workspace-viewer">
              {activeLoading ? <p className="meta">Loading…</p> : null}
              {activeError ? <p className="meta is-error">{activeError}</p> : null}
              {activeContent != null && !activeLoading ? (
                <CodeEditor code={activeContent} />
              ) : null}
            </div>
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
