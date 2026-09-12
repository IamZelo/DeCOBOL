import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { convert } from '../api/client'
import type { ConvertOptions } from '../types'

export type TargetRuntime = 'java_21' | 'java_17'
export type PrecisionMode = 'big_decimal' | 'native'

interface ConversionState {
  javaPackage: string
  runtime: TargetRuntime
  precision: PrecisionMode
  confirmLocal: boolean
  jobId: string | null
  submitting: boolean
  submitError: string | null
  setJavaPackage: (value: string) => void
  setRuntime: (value: TargetRuntime) => void
  setPrecision: (value: PrecisionMode) => void
  setConfirmLocal: (value: boolean) => void
  /**
   * Submits one /api/convert job per selected path. The first becomes the
   * "live" job the Pipeline/Diff pages track; any others are fired
   * fire-and-forget and show up in Job History once they finish — v1 has one
   * live pipeline view at a time, matching the Figma design, not a
   * multi-job dashboard.
   */
  startConversion: (sourcePaths: string[]) => Promise<string | null>
}

const Ctx = createContext<ConversionState | null>(null)

const JOB_ID_KEY = 'decobol.lastJobId'

function readStoredJobId(): string | null {
  try {
    return sessionStorage.getItem(JOB_ID_KEY)
  } catch {
    return null
  }
}

export function ConversionProvider({ children }: { children: ReactNode }) {
  const [javaPackage, setJavaPackage] = useState('com.legacy.bank.refactored')
  const [runtime, setRuntime] = useState<TargetRuntime>('java_21')
  const [precision, setPrecision] = useState<PrecisionMode>('big_decimal')
  const [confirmLocal, setConfirmLocal] = useState(true)
  // Persisted so a hard reload (or a direct link to /diff or /pipeline)
  // doesn't lose track of the job that's actually running or just finished —
  // this is in-memory-only React state otherwise, and a full navigation
  // remounts the whole app.
  const [jobId, setJobIdState] = useState<string | null>(readStoredJobId)
  const setJobId = useCallback((id: string | null) => {
    setJobIdState(id)
    try {
      if (id) sessionStorage.setItem(JOB_ID_KEY, id)
      else sessionStorage.removeItem(JOB_ID_KEY)
    } catch {
      /* sessionStorage unavailable (private mode etc.) — jobId still works in-memory */
    }
  }, [])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const startConversion = useCallback(
    async (sourcePaths: string[]) => {
      const [primary, ...rest] = sourcePaths
      if (!primary) return null
      setSubmitting(true)
      setSubmitError(null)
      const options: ConvertOptions = {
        java_package: javaPackage,
        target_runtime: runtime,
        precision_mode: precision,
      }
      try {
        const res = await convert({ source_path: primary, options })
        setJobId(res.job_id)
        for (const path of rest) {
          convert({ source_path: path, options }).catch(() => {
            /* background jobs surface in Job History regardless */
          })
        }
        return res.job_id
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : String(err))
        return null
      } finally {
        setSubmitting(false)
      }
    },
    [javaPackage, precision, runtime],
  )

  const value: ConversionState = {
    javaPackage,
    runtime,
    precision,
    confirmLocal,
    jobId,
    submitting,
    submitError,
    setJavaPackage,
    setRuntime,
    setPrecision,
    setConfirmLocal,
    startConversion,
  }

  return createElement(Ctx.Provider, { value }, children)
}

export function useConversion() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useConversion must be used inside ConversionProvider')
  return ctx
}
