import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { convert } from '../api/client'
import { DEFAULT_SELECTION, SOURCE_FILES } from '../data/fixtures'
import type { ConvertOptions, SourceFile } from '../types'

export type TargetRuntime = 'java_21' | 'java_17'
export type PrecisionMode = 'big_decimal' | 'native'

interface ConversionState {
  files: SourceFile[]
  selected: string[]
  activePath: string
  javaPackage: string
  runtime: TargetRuntime
  precision: PrecisionMode
  confirmLocal: boolean
  jobId: string | null
  submitting: boolean
  submitError: string | null
  selectedFiles: SourceFile[]
  toggleSelected: (path: string) => void
  setSelection: (paths: string[]) => void
  setActivePath: (path: string) => void
  setJavaPackage: (value: string) => void
  setRuntime: (value: TargetRuntime) => void
  setPrecision: (value: PrecisionMode) => void
  setConfirmLocal: (value: boolean) => void
  startConversion: () => Promise<string | null>
}

const Ctx = createContext<ConversionState | null>(null)

export function ConversionProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<string[]>(DEFAULT_SELECTION)
  const [activePath, setActivePath] = useState('jcl/PAYROLL01.cbl')
  const [javaPackage, setJavaPackage] = useState('com.legacy.bank.refactored')
  const [runtime, setRuntime] = useState<TargetRuntime>('java_21')
  const [precision, setPrecision] = useState<PrecisionMode>('big_decimal')
  const [confirmLocal, setConfirmLocal] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const toggleSelected = useCallback((path: string) => {
    setSelected((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path],
    )
  }, [])

  const selectedFiles = useMemo(
    () => SOURCE_FILES.filter((f) => selected.includes(f.path)),
    [selected],
  )

  const startConversion = useCallback(async () => {
    const primary =
      selectedFiles.find((f) => f.cobol_code) ?? selectedFiles[0] ?? null
    if (!primary) return null
    setSubmitting(true)
    setSubmitError(null)
    const options: ConvertOptions = {
      java_package: javaPackage,
      target_runtime: runtime,
      precision_mode: precision,
    }
    try {
      const res = await convert({
        cobol_code: primary.cobol_code,
        filename: primary.name,
        options,
      })
      setJobId(res.job_id)
      return res.job_id
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setSubmitting(false)
    }
  }, [javaPackage, precision, runtime, selectedFiles])

  const value: ConversionState = {
    files: SOURCE_FILES,
    selected,
    activePath,
    javaPackage,
    runtime,
    precision,
    confirmLocal,
    jobId,
    submitting,
    submitError,
    selectedFiles,
    toggleSelected,
    setSelection: setSelected,
    setActivePath,
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
