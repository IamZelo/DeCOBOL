import type { DiffLine } from '../lib/diff'

interface Side {
  name: string
  meta: string
  lines: number
  rows: DiffLine[]
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
        <div className="diff-head-cell">
          <div className="diff-head-id">
            <b>{source.name}</b>
            <span className="meta">{source.meta}</span>
          </div>
          <span className="meta">{source.lines} lines</span>
        </div>
        <div className="diff-head-cell">
          <div className="diff-head-id">
            <b>{target.name}</b>
            <span className="meta">{target.meta}</span>
          </div>
          <span className="meta">{target.lines} lines</span>
        </div>
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
