import type {
  ConvertOptions,
  FsFile,
  FsTree,
  Health,
  Job,
  JobSummary,
  RepoGraphPayload,
} from '../types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.error ?? `${path} → ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function getHealth() {
  return get<Health>('/api/health')
}

export function listJobs() {
  return get<{ jobs: JobSummary[] }>('/api/jobs')
}

export function getJob(jobId: string) {
  return get<Job>(`/api/jobs/${jobId}`)
}

/** `GET /api/fs/tree` — docs/LOCAL_DEPLOYMENT_WORKFLOW.md (additive). */
export function getFsTree(path = '', root: 'input' | 'output' = 'input') {
  const qs = new URLSearchParams({ path, root })
  return get<FsTree>(`/api/fs/tree?${qs}`)
}

/** `GET /api/fs/file` — docs/LOCAL_DEPLOYMENT_WORKFLOW.md (additive). */
export function getFsFile(path: string, root: 'input' | 'output' = 'input') {
  const qs = new URLSearchParams({ path, root })
  return get<FsFile>(`/api/fs/file?${qs}`)
}

/**
 * `GET /api/fs/graph` — parses every COBOL file under the workspace and
 * returns the cross-file dependency graph (docs/LOCAL_DEPLOYMENT_WORKFLOW.md,
 * additive).
 */
export function getFsGraph(path = '', root: 'input' | 'output' = 'input', recursive = true) {
  const qs = new URLSearchParams({ path, root, recursive: String(recursive) })
  return get<RepoGraphPayload>(`/api/fs/graph?${qs}`)
}

type ConvertRequest =
  | { source_path: string; cobol_code?: undefined; filename?: undefined }
  | { cobol_code: string; filename?: string; source_path?: undefined }

export async function convert(
  body: ConvertRequest & { options?: ConvertOptions },
): Promise<{ job_id: string; status: string }> {
  const res = await fetch('/api/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, wait: false }),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => null)
    throw new Error(errBody?.error ?? `/api/convert → ${res.status}`)
  }
  return res.json()
}

/** `POST /api/convert/batch` — docs/LOCAL_DEPLOYMENT_WORKFLOW.md (additive). */
export async function convertBatch(body: {
  source_dir: string
  recursive?: boolean
  options?: ConvertOptions
}): Promise<{ jobs: { job_id: string; source_path: string; status: string }[] }> {
  const res = await fetch('/api/convert/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => null)
    throw new Error(errBody?.error ?? `/api/convert/batch → ${res.status}`)
  }
  return res.json()
}

export function eventStreamUrl(jobId: string) {
  return `/api/jobs/${jobId}/events`
}
