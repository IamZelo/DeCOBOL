import { splitCobolLine } from '../lib/format'

/** Read-only COBOL source viewer with the sequence-number gutter. */
export function CodeEditor({ code }: { code: string }) {
  const lines = code.split('\n')

  return (
    <div className="viewer">
      {lines.map((text, i) => {
        const { keyword, rest, isComment } = splitCobolLine(text)
        return (
          <div className="viewer-line" key={i}>
            <span className={isComment ? 'viewer-no is-dim' : 'viewer-no'}>
              {String((i + 1) * 100).padStart(6, '0')}
            </span>
            <span className={isComment ? 'viewer-code is-comment' : 'viewer-code'}>
              {keyword ? <b>{keyword}</b> : null}
              {rest}
            </span>
          </div>
        )
      })}
    </div>
  )
}
