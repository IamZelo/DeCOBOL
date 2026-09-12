import { useEffect, useRef, useState } from 'react'
import { eventStreamUrl } from '../api/client'
import type { JobEvent } from '../types'

/**
 * Live event stream for a job. Orders and de-duplicates by `seq` so that an SSE
 * reconnect cannot scramble the log (CONTRACTS §6).
 */
export function useJobEvents(jobId: string | null) {
  const [events, setEvents] = useState<JobEvent[]>([])
  const [connected, setConnected] = useState(false)
  const seen = useRef(new Set<number>())

  useEffect(() => {
    seen.current = new Set()
    setEvents([])
    if (!jobId) return

    const source = new EventSource(eventStreamUrl(jobId))
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = (msg) => {
      let event: JobEvent
      try {
        event = JSON.parse(msg.data)
      } catch {
        return
      }
      if (seen.current.has(event.seq)) return
      seen.current.add(event.seq)
      setEvents((prev) => [...prev, event].sort((a, b) => a.seq - b.seq))
    }

    return () => {
      source.close()
      setConnected(false)
    }
  }, [jobId])

  return { events, connected }
}
