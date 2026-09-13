import { useCallback, useEffect, useState } from 'react'
import { getFsGraph } from '../api/client'
import { buildRepoGraph, type RepoDependencyGraph } from '../lib/repoGraph'

/**
 * Loads the whole-workspace dependency graph. Called on workspace entry, so
 * the graph is populated from every COBOL file under the input root before any
 * conversion job exists — it does not depend on a job's `parsed_ast`.
 *
 * `activePath` only restyles the matching node, so changing the open file does
 * not refetch the scan.
 */
export function useRepoGraph(activePath?: string | null) {
  const [graph, setGraph] = useState<RepoDependencyGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getFsGraph('', 'input', true)
      .then((payload) => !cancelled && setGraph(buildRepoGraph(payload, activePath)))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
    // activePath is applied below, not a refetch trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick])

  useEffect(() => {
    setGraph((prev) =>
      prev
        ? {
            ...prev,
            nodes: prev.nodes.map((n) => {
              const path = prev.pathById.get(n.id) ?? null
              const active = activePath != null && path === activePath
              return active === (n.active === true) ? n : { ...n, active }
            }),
          }
        : prev,
    )
  }, [activePath])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  return { graph, loading, error, reload }
}
