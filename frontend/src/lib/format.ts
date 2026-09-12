export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

export function formatSeconds(ms: number | null): string {
  if (ms == null) return '—'
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatClock(ts: number): string {
  const d = new Date(ts * 1000)
  const pad = (n: number, w = 2) => String(n).padStart(w, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(
    d.getMilliseconds(),
    3,
  )}`
}

export function formatTimestamp(ts: number): string {
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

/** COBOL reserved words the Figma source viewer renders in bold. */
const COBOL_KEYWORDS =
  /^(IDENTIFICATION DIVISION|ENVIRONMENT DIVISION|DATA DIVISION|PROCEDURE DIVISION|CONFIGURATION SECTION|WORKING-STORAGE SECTION|PROGRAM-ID|SOURCE-COMPUTER|COPY|PERFORM)\b/

export function splitCobolLine(text: string): {
  keyword: string
  rest: string
  isComment: boolean
} {
  if (text.trimStart().startsWith('*')) {
    return { keyword: '', rest: text, isComment: true }
  }
  const match = text.match(COBOL_KEYWORDS)
  if (!match) return { keyword: '', rest: text, isComment: false }
  return {
    keyword: match[0],
    rest: text.slice(match[0].length),
    isComment: false,
  }
}
