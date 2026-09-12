import { useMemo, useState } from 'react'
import { useWorkspace, type TreeNode } from '../hooks/useWorkspace'
import { formatBytes } from '../lib/format'

function Checkbox({ checked }: { checked: boolean }) {
  return (
    <span className={checked ? 'tick is-on' : 'tick'} aria-hidden="true">
      {checked ? (
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
  )
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 14 11" width="13" height="10" aria-hidden="true">
      <path
        d="M.6.6h4.1l1.2 1.5h7.5v8.3H.6z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
      />
    </svg>
  )
}

function collectFilePaths(node: TreeNode): string[] {
  if (node.type === 'file') return [node.path]
  return (node.children ?? []).flatMap(collectFilePaths)
}

function matchesFilter(node: TreeNode, needle: string): boolean {
  if (!needle) return true
  if (node.name.toLowerCase().includes(needle)) return true
  if (node.type === 'dir' && node.children) {
    return node.children.some((c) => matchesFilter(c, needle))
  }
  return false
}

function TreeRow({ node, depth, needle }: { node: TreeNode; depth: number; needle: string }) {
  const { selected, activePath, toggleDir, toggleSelected, setActivePath } = useWorkspace()

  if (!matchesFilter(node, needle)) return null

  if (node.type === 'dir') {
    const filePaths = collectFilePaths(node)
    const allSelected = filePaths.length > 0 && filePaths.every((p) => selected.includes(p))
    return (
      <div className="tree-group">
        <div className="tree-dir" style={{ paddingLeft: 12 + depth * 16 }}>
          <button
            className="tree-check"
            onClick={() => {
              filePaths.forEach((p) => {
                const isSelected = selected.includes(p)
                if (allSelected === isSelected) toggleSelected(p)
              })
            }}
            aria-label={`Select all in ${node.name}`}
          >
            <Checkbox checked={allSelected} />
          </button>
          <button className="tree-disclosure" onClick={() => toggleDir(node.path)}>
            <span className="tree-folder">
              <FolderIcon />
            </span>
            <span className="tree-dir-name">{node.name}/</span>
            {node.loading ? <span className="meta">…</span> : null}
          </button>
        </div>
        {node.expanded && node.children
          ? node.children.map((child) => (
              <TreeRow key={child.path} node={child} depth={depth + 1} needle={needle} />
            ))
          : null}
      </div>
    )
  }

  const isActive = node.path === activePath
  return (
    <div
      className={isActive ? 'tree-file is-active' : 'tree-file'}
      style={{ paddingLeft: 20 + depth * 16 }}
    >
      <button
        className="tree-check"
        onClick={() => toggleSelected(node.path)}
        aria-label={`Select ${node.name}`}
      >
        <Checkbox checked={selected.includes(node.path)} />
      </button>
      <button className="tree-file-name" onClick={() => setActivePath(node.path)}>
        {node.name}
      </button>
      <span className={isActive ? 'tree-file-tag' : 'meta'}>
        {isActive ? 'viewing' : node.size != null ? formatBytes(node.size) : ''}
      </span>
    </div>
  )
}

export function UploadPanel() {
  const { tree, loading, error, root, selectAllFiles, clearSelection } = useWorkspace()
  const [filter, setFilter] = useState('')
  const needle = filter.trim().toLowerCase().replace(/\*/g, '')

  const fileCount = useMemo(
    () => tree.reduce((n, node) => n + collectFilePaths(node).length, 0),
    [tree],
  )

  return (
    <aside className="explorer">
      <div className="explorer-search">
        <div className="explorer-input">
          <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
            <circle
              cx="5"
              cy="5"
              r="3.6"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
            />
            <path
              d="M7.8 7.8 11 11"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </svg>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter files (e.g. *.cbl)..."
            aria-label="Filter files"
          />
        </div>
        <div className="explorer-subbar">
          <div className="explorer-actions">
            <button onClick={selectAllFiles}>Select all</button>
            <span>·</span>
            <button onClick={clearSelection}>Clear</button>
          </div>
          <span className="meta">{fileCount} files found</span>
        </div>
        {root ? <span className="meta explorer-root">{root}</span> : null}
      </div>

      <div className="explorer-tree">
        {loading ? <p className="meta explorer-status">Loading workspace…</p> : null}
        {error ? <p className="meta explorer-status is-error">{error}</p> : null}
        {!loading && !error && tree.length === 0 ? (
          <p className="meta explorer-status">No files under the input root.</p>
        ) : null}
        {tree.map((node) => (
          <TreeRow key={node.path} node={node} depth={0} needle={needle} />
        ))}
      </div>
    </aside>
  )
}
