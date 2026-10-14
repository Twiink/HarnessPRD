import type { RunSummary } from '../types';
import type { JobStreamHandlers } from '../types/job';
import { StreamError } from '../services/api';

export async function readJobStream(
  jobId: string,
  handlers: JobStreamHandlers,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(`/api/jobs/${jobId}/stream`, { signal });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new StreamError(typeof err.detail === 'string' ? err.detail : 'Request failed');
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: unknown = null;
  let streamError: StreamError | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') break;

      const event = JSON.parse(data);
      if (event.type === 'error') {
        streamError = new StreamError(
          event.message || 'Request failed',
          event.code,
          event.request_id,
        );
        continue;
      }
      if (event.type === 'snapshot') {
        handlers.onSnapshot?.(event);
        continue;
      }
      if (event.type === 'chunk' || event.type === 'text_delta') {
        handlers.onChunk?.(event.content);
      } else if (event.type === 'phase') {
        handlers.onPhase?.(event.phase);
      } else if (event.type === 'review') {
        handlers.onReview?.(event.content);
      } else if (event.type === 'run_summary') {
        const { type: _type, ...summary } = event;
        handlers.onRunSummary?.(summary as RunSummary);
      } else if (event.type === 'done') {
        result = event;
      }
    }
  }

  if (streamError) throw streamError;
  return result;
}
