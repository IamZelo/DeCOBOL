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

export interface ConversionBatchJob {
  job_id: string
  source_path: string
  filename: string
}

interface ConversionState {
  javaPackage: string
  runtime: TargetRuntime
  precision: PrecisionMode
  confirmLocal: boolean
  jobId: string | null
  batchJobs: ConversionBatchJob[]
  submitting: boolean
  submitError: string | null
  setJavaPackage: (value: string) => void
  setRuntime: (value: TargetRuntime) => void
  setPrecision: (value: PrecisionMode) => void
  setConfirmLocal: (value: boolean) => void
  setActiveJobId: (jobId: string) => void
  /** Submits one /api/convert job per selected path and keeps the full batch. */
  startConversion: (sourcePaths: string[]) => Promise<string | null>
}

const Ctx = createContext<ConversionState | null>(null)

const JOB_ID_KEY = 'decobol.lastJobId'
const BATCH_JOBS_KEY = 'decobol.batchJobs'

function readStoredJobId(): string | null {
  try {
    return sessionStorage.getItem(JOB_ID_KEY)
  } catch {
    return null
  }
}

function readStoredBatchJobs(): ConversionBatchJob[] {
  try {
    const raw = sessionStorage.getItem(BATCH_JOBS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ConversionBatchJob[]
    return Array.isArray(parsed) ? parsed.filter((j) => j.job_id && j.source_path) : []
  } catch {
    return []
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
  const [batchJobs, setBatchJobsState] = useState<ConversionBatchJob[]>(readStoredBatchJobs)
  const setBatchJobs = useCallback((jobs: ConversionBatchJob[]) => {
    setBatchJobsState(jobs)
    try {
      if (jobs.length) sessionStorage.setItem(BATCH_JOBS_KEY, JSON.stringify(jobs))
      else sessionStorage.removeItem(BATCH_JOBS_KEY)
    } catch {
      /* sessionStorage unavailable — batch state still works in-memory */
    }
  }, [])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const setActiveJobId = useCallback(
    (id: string) => {
      setJobId(id)
    },
    [setJobId],
  )

  const startConversion = useCallback(
    async (sourcePaths: string[]) => {
      if (!sourcePaths.length) return null
      setSubmitting(true)
      setSubmitError(null)
      setBatchJobs([])
      const options: ConvertOptions = {
        java_package: javaPackage,
        target_runtime: runtime,
        precision_mode: precision,
      }
      try {
        const settled = await Promise.allSettled(
          sourcePaths.map(async (path) => {
            const res = await convert({ source_path: path, options })
            return {
              job_id: res.job_id,
              source_path: path,
              filename: path.split('/').pop() || path,
            }
          }),
        )

        const submitted = settled
          .filter((r): r is PromiseFulfilledResult<ConversionBatchJob> => r.status === 'fulfilled')
          .map((r) => r.value)
        const failures = settled.filter((r) => r.status === 'rejected')

        if (!submitted.length) {
          const firstError = failures[0]
          throw firstError?.reason ?? new Error('No conversion jobs were submitted.')
        }

        setBatchJobs(submitted)
        setJobId(submitted[0].job_id)

        if (failures.length) {
          setSubmitError(`${failures.length} file${failures.length === 1 ? '' : 's'} could not be submitted.`)
        }

        return submitted[0].job_id
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : String(err))
        return null
      } finally {
        setSubmitting(false)
      }
    },
    [javaPackage, precision, runtime, setBatchJobs, setJobId],
  )

  const value: ConversionState = {
    javaPackage,
    runtime,
    precision,
    confirmLocal,
    jobId,
    batchJobs,
    submitting,
    submitError,
    setJavaPackage,
    setRuntime,
    setPrecision,
    setConfirmLocal,
    setActiveJobId,
    startConversion,
  }

  return createElement(Ctx.Provider, { value }, children)
}

export function useConversion() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useConversion must be used inside ConversionProvider')
  return ctx
}
