import { useEffect, useRef } from 'react'

export interface LogLine {
  ts: string
  text: string
  tone: 'dim' | 'accent' | 'bright'
}

export function ExecutionLog({
  lines,
  wrap,
  autoscroll,
}: {
  lines: LogLine[]
  wrap: boolean
  autoscroll: boolean
}) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (autoscroll && el) el.scrollTop = el.scrollHeight
  }, [lines, autoscroll])

  return (
    <div className="log-scroll" ref={scrollRef}>
      <div className={wrap ? 'log is-wrapped' : 'log'}>
        {lines.map((line, i) => (
          <div className="log-line" key={i}>
            <span className="log-ts">{line.ts}</span>
            <span className={`log-text is-${line.tone}`}>
              {line.text}
              {i === lines.length - 1 ? <span className="caret" /> : null}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
