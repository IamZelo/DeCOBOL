import type { DiffLine } from '../lib/diff'
import { IconFile } from './icons'

interface Badge {
  label: string
  tone: 'neutral' | 'success' | 'warning'
}

interface Side {
  name: string
  meta: string
  lines: number
  rows: DiffLine[]
  badge?: Badge
}

function Column({ rows }: { rows: DiffLine[] }) {
  return (
    <div className="diff-col">
      {rows.map((row) => (
        <div className={`diff-row is-${row.emphasis}`} key={row.n}>
          <span className="diff-no">{row.n}</span>
          <span className="diff-code">{row.text}</span>
        </div>
      ))}
    </div>
  )
}

function HeadCell({ side }: { side: Side }) {
  return (
    <div className="diff-head-cell">
      <div className="diff-head-id">
        <IconFile />
        <b>{side.name}</b>
        <span className="meta">{side.meta}</span>
      </div>
      <div className="diff-head-right">
        <span className="meta">{side.lines} lines</span>
        {side.badge ? <span className={`badge is-${side.badge.tone}`}>{side.badge.label}</span> : null}
      </div>
    </div>
  )
}

export function DiffView({
  source,
  target,
  mode,
}: {
  source: Side
  target: Side
  mode: 'split' | 'unified'
}) {
  return (
    <div className="diff">
      <div className="diff-head">
        <HeadCell side={source} />
        <HeadCell side={target} />
      </div>

      {mode === 'split' ? (
        <div className="diff-body">
          <Column rows={source.rows} />
          <Column rows={target.rows} />
        </div>
      ) : (
        <div className="diff-body is-unified">
          <Column rows={[...source.rows, ...target.rows]} />
        </div>
      )}
    </div>
  )
}
