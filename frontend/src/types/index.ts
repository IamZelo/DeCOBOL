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

/** CONTRACTS §3.5 — a subset; only the fields the dependency graph needs. */
export interface AstParagraph {
  name: string
  section: string | null
  performs: string[]
  start_line: number
  end_line: number
}

/** CONTRACTS §3.3 — a subset; only the fields the structure view needs. */
export interface AstVariable {
  name: string
  level: number
  parent: string | null
  pic: string | null
  usage: string
  is_group: boolean
  java_name: string
  java_type: string
  source_line: number
}

/** CONTRACTS §3.7 */
export interface AstCopybook {
  name: string
  mechanism: 'COPY' | 'EXEC_SQL_INCLUDE'
  resolved: boolean
  source_line: number
}

/** CONTRACTS §3.4 */
export interface AstFileDescriptor {
  cobol_name: string
  assign_to: string
  organization: string
  operations: string[]
}

/** CONTRACTS §3.8 — a subset. */
export interface AstSqlBlock {
  operation: string
  tables: string[]
  paragraph: string | null
}

/** CONTRACTS §3.2 — a subset; only the fields the dependency graph needs. */
export interface ParsedAst {
  program_id: string
  paragraphs: AstParagraph[]
  copybooks: AstCopybook[]
  files: AstFileDescriptor[]
  sql_blocks: AstSqlBlock[]
  variables?: AstVariable[]
  [key: string]: unknown
}

export interface JobResult {
  program_id: string
  class_name: string
  /** Already resolved to optimized_code-else-java_code by the backend (§11). */
  java_code: string
  validation: Validation | null
  documentation: Documentation | null
  parsed_ast: ParsedAst | null
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
  /** Additive per docs/LOCAL_DEPLOYMENT_WORKFLOW.md — null for inline cobol_code jobs. */
  source_path: string | null
  /** Set once a source_path job finishes; null until then and for inline jobs. */
  output_path: string | null
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

export interface SourceFile {
  path: string
  name: string
  dir: string
  size_bytes: number
  lines: number
  linkage: string
  cobol_code: string
}

/** `GET /api/fs/tree` entry (docs/LOCAL_DEPLOYMENT_WORKFLOW.md, additive). */
export interface FsEntry {
  name: string
  type: 'file' | 'dir'
  size?: number
}

export interface FsTree {
  root: string
  path: string
  entries: FsEntry[]
}

/** `GET /api/fs/file` response. */
export interface FsFile {
  path: string
  root: 'input' | 'output'
  content: string
  size: number
}
