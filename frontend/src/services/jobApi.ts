import { StreamError } from './api';
import type { JobArtifact, JobSnapshot } from '../types/job';

async function parseError(response: Response): Promise<StreamError> {
  const payload = await response.json().catch(() => ({ detail: 'Request failed' }));
  const detail = payload?.detail;
  if (typeof detail === 'string') {
    return new StreamError(detail);
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return new StreamError(detail.message);
  }
  return new StreamError('Request failed');
}

export async function createJob(
  sessionId: string,
  artifact: JobArtifact,
  payload: Record<string, unknown>,
): Promise<{ job_id: string }> {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, artifact, payload }),
  });
  if (!res.ok) {
    throw await parseError(res);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobSnapshot> {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) {
    throw await parseError(res);
  }
  return res.json();
}
