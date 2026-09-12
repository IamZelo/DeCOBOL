import { useMemo, useState } from 'react'
import { useConversion } from '../hooks/useConversion'
import { formatBytes } from '../lib/format'
import type { SourceFile } from '../types'

function Checkbox({ checked }: { checked: boolean }) {
  return (
    <span className={checked ? 'tick is-on' : 'tick'} aria-hidden="true">
      {checked ? (
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

export function UploadPanel() {
  const {
    files,
    selected,
    activePath,
    toggleSelected,
    setSelection,
    setActivePath,
  } = useConversion()
  const [filter, setFilter] = useState('')

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase().replace(/\*/g, '')
    if (!needle) return files
    return files.filter((f) => f.path.toLowerCase().includes(needle))
  }, [files, filter])

  const groups = useMemo(() => {
    const byDir = new Map<string, SourceFile[]>()
    for (const file of visible) {
      const list = byDir.get(file.dir) ?? []
      list.push(file)
      byDir.set(file.dir, list)
    }
    return [...byDir.entries()]
  }, [visible])

  const allSelectedIn = (items: SourceFile[]) =>
    items.length > 0 && items.every((f) => selected.includes(f.path))

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
            <button onClick={() => setSelection(files.map((f) => f.path))}>
              Select all
            </button>
            <span>·</span>
            <button onClick={() => setSelection([])}>Clear</button>
          </div>
          <span className="meta">{visible.length} files found</span>
        </div>
      </div>

      <div className="explorer-tree">
        {groups.map(([dir, items]) => (
          <div className="tree-group" key={dir}>
            <div className="tree-dir">
              <button
                className="tree-check"
                onClick={() =>
                  setSelection(
                    allSelectedIn(items)
                      ? selected.filter((p) => !items.some((f) => f.path === p))
                      : [
                          ...new Set([
                            ...selected,
                            ...items.map((f) => f.path),
                          ]),
                        ],
                  )
                }
                aria-label={`Select all in ${dir}`}
              >
                <Checkbox checked={allSelectedIn(items)} />
              </button>
              <span className="tree-folder">
                <FolderIcon />
              </span>
              <span className="tree-dir-name">{dir}</span>
            </div>

            <div className="tree-files">
              {items.map((file) => {
                const isActive = file.path === activePath
                return (
                  <div
                    key={file.path}
                    className={isActive ? 'tree-file is-active' : 'tree-file'}
                  >
                    <button
                      className="tree-check"
                      onClick={() => toggleSelected(file.path)}
                      aria-label={`Select ${file.name}`}
                    >
                      <Checkbox checked={selected.includes(file.path)} />
                    </button>
                    <button
                      className="tree-file-name"
                      onClick={() => setActivePath(file.path)}
                    >
                      {file.name}
                    </button>
                    <span className={isActive ? 'tree-file-tag' : 'meta'}>
                      {isActive ? 'viewing' : formatBytes(file.size_bytes)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
