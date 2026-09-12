// Mirrors docs/CONTRACTS.md v1.0.0 verbatim — snake_case, no translation layer.

export type JobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'

export type Severity = 'error' | 'warning' | 'info'

export type EventType =
  | 'agent_started'
  | 'agent_finished'
  | 'tool_called'
  | 'tool_result'
  | 'llm_called'
  | 'llm_replied'
  | 'decision'
  | 'error'
  | 'pipeline_started'
  | 'pipeline_finished'
  | 'retry_scheduled'

export interface JobEvent {
  seq: number
  ts: number
  job_id: string
  type: EventType | string
  agent: string | null
  message: string
  data: Record<string, unknown>
}

export interface Finding {
  check: string
  severity: Severity
  message: string
  cobol_ref: string | null
  cobol_line?: number | null
  java_line?: number | null
  suggestion?: string | null
}

export interface CompileDiagnostic {
  file: string
  line: number
  column: number
  severity: Severity
  message: string
}

export interface CompileResult {
  success: boolean
  exit_code: number
  stdout: string
  stderr: string
  diagnostics: CompileDiagnostic[]
  skipped: boolean
  skip_reason: string | null
}

export interface Validation {
  passed: boolean
  compile: CompileResult
  findings: Finding[]
  counts: { error: number; warning: number; info: number }
  attempt: number
}

export interface VariableMapping {
  cobol_name: string
  pic: string
  usage: string
  java_name: string
  java_type: string
  note?: string | null
}

export interface Documentation {
  class_javadoc: string
  variable_map: VariableMapping[]
  migration_notes: string[]
  unsupported: { feature: string; count: number; detail: string }[]
}

export interface JobResult {
  program_id: string
  class_name: string
  /** Already resolved to optimized_code-else-java_code by the backend (§11). */
  java_code: string
  validation: Validation | null
  documentation: Documentation | null
  parsed_ast: Record<string, unknown> | null
}

export interface AgentResultSummary {
  agent: string
  status: string
  next_action: string
  confidence?: number
  duration_ms?: number
  used_fallback?: boolean
}

export interface Job {
  job_id: string
  status: JobStatus
  filename: string | null
  created_ts: number
  finished_ts: number | null
  duration_ms: number | null
  retry_count: number
  raw_cobol?: string
  result: JobResult | null
  agent_results?: AgentResultSummary[]
  errors?: { message: string }[]
  events?: JobEvent[]
}

/** `GET /api/jobs` — same object minus raw_cobol, result, events, agent_results. */
export type JobSummary = Omit<
  Job,
  'raw_cobol' | 'result' | 'events' | 'agent_results'
>

export interface Health {
  status: 'ok' | 'degraded'
  llm: { reachable: boolean; model: string; base_url: string; mock: boolean }
  javac: { available: boolean; version: string | null }
  contract_version: string
}

export interface ConvertOptions {
  java_package?: string
  target_runtime?: string
  precision_mode?: string
  [key: string]: unknown
}

/** Local-only: a COBOL file staged in the workspace explorer. */
export interface SourceFile {
  path: string
  name: string
  dir: string
  size_bytes: number
  lines: number
  /** Human note shown under the name on the Convert screen. */
  linkage: string
  cobol_code: string
}
