import type { GeneratePrdStreamResult, PrdReviewResult } from './index';
import type { StreamHandlers } from '../services/api';

export type GenerationJobArtifact = 'prd' | 'api-docs' | 'prompts';

export type OptimizeJobArtifact = 'optimize-prd' | 'optimize-api-docs' | 'optimize-prompts';

export type JobArtifact = GenerationJobArtifact | OptimizeJobArtifact;

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export type JobPhase = 'writing' | 'reviewing' | 'rewriting' | 'generating' | 'done';

export type JobSnapshot = {
  id: string;
  session_id: string;
  artifact: JobArtifact;
  status: JobStatus;
  phase: JobPhase;
  draft_content: string;
  review?: PrdReviewResult | null;
  result?: GeneratePrdStreamResult | Record<string, unknown> | null;
  error?: string | null;
};

export type JobSnapshotEvent = {
  type: 'snapshot';
  status: JobStatus;
  phase: JobPhase;
  artifact: JobArtifact;
  draft_content: string;
  review?: PrdReviewResult | null;
};

export type JobStreamHandlers = StreamHandlers & {
  onSnapshot?: (snap: JobSnapshotEvent) => void;
  onChunk?: (chunk: string) => void;
};
