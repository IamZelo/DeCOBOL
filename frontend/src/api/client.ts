import type { ConvertOptions, Health, Job, JobSummary } from '../types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`${path} → ${res.status}`)
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

export async function convert(body: {
  cobol_code: string
  filename?: string
  options?: ConvertOptions
}): Promise<{ job_id: string; status: string }> {
  const res = await fetch('/api/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, wait: false }),
  })
  if (!res.ok) throw new Error(`/api/convert → ${res.status}`)
  return res.json()
}

export function eventStreamUrl(jobId: string) {
  return `/api/jobs/${jobId}/events`
}
