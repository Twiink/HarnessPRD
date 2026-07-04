import type { V2ViewState } from '../services/sessionService';
import type { DocType } from '../types';
import type { JobArtifact, GenerationJobArtifact, OptimizeJobArtifact } from '../types/job';
import {
  finalizePrdStepsFromSummary,
  mapPrdPhaseToSteps,
  markApiDocsStepsDone,
  markPromptsStepsDone,
} from './generationSteps';
import type { RunSummary } from '../types';
import type { StepItem } from '../components/GenerationStepper';

export function isOptimizeArtifact(artifact: JobArtifact): artifact is OptimizeJobArtifact {
  return artifact.startsWith('optimize-');
}

export function contentArtifactFromOptimize(artifact: OptimizeJobArtifact): GenerationJobArtifact {
  if (artifact === 'optimize-api-docs') return 'api-docs';
  if (artifact === 'optimize-prompts') return 'prompts';
  return 'prd';
}

export function contentArtifactFromJob(artifact: JobArtifact): GenerationJobArtifact {
  if (isOptimizeArtifact(artifact)) {
    return contentArtifactFromOptimize(artifact);
  }
  return artifact;
}

export function optimizeArtifactFor(docType: DocType): OptimizeJobArtifact {
  if (docType === 'api-docs') return 'optimize-api-docs';
  if (docType === 'prompts') return 'optimize-prompts';
  return 'optimize-prd';
}

export function docTypeFromOptimizeArtifact(artifact: OptimizeJobArtifact): DocType {
  if (artifact === 'optimize-api-docs') return 'api-docs';
  if (artifact === 'optimize-prompts') return 'prompts';
  return 'prd';
}

export function generatingViewFor(artifact: JobArtifact): V2ViewState {
  const contentArtifact = contentArtifactFromJob(artifact);
  if (contentArtifact === 'api-docs') return 'generating-api-docs';
  if (contentArtifact === 'prompts') return 'generating-prompts';
  return 'generating-prd';
}

export function reviewViewFor(artifact: JobArtifact): V2ViewState {
  const contentArtifact = contentArtifactFromJob(artifact);
  if (contentArtifact === 'api-docs') return 'review-api-docs';
  if (contentArtifact === 'prompts') return 'review-prompts';
  return 'review-prd';
}

export function jobPhaseToSsePhase(phase: import('../types/job').JobPhase): string | null {
  if (phase === 'writing') return 'writer_started';
  if (phase === 'reviewing') return 'review_started';
  if (phase === 'rewriting') return 'rewrite_started';
  return null;
}

export function finalizeStepsForArtifact(
  artifact: GenerationJobArtifact,
  summary: RunSummary,
): StepItem[] {
  if (artifact === 'prd') return finalizePrdStepsFromSummary(summary);
  if (artifact === 'api-docs') return markApiDocsStepsDone();
  return markPromptsStepsDone();
}

export function restoreStepperFromJobPhase(
  artifact: JobArtifact,
  phase: import('../types/job').JobPhase,
  mapPrd: (p: string) => StepItem[],
): StepItem[] | null {
  if (contentArtifactFromJob(artifact) !== 'prd') return null;
  const ssePhase = jobPhaseToSsePhase(phase);
  if (!ssePhase) return null;
  return mapPrd(ssePhase);
}

export type ContentSetters = {
  setPrdContent: (v: string) => void;
  setApiDocsContent: (v: string) => void;
  setPromptsContent: (v: string) => void;
};

export function setContentForArtifact(
  artifact: JobArtifact,
  content: string,
  setters: ContentSetters,
) {
  const contentArtifact = contentArtifactFromJob(artifact);
  if (contentArtifact === 'api-docs') {
    setters.setApiDocsContent(content);
    return;
  }
  if (contentArtifact === 'prompts') {
    setters.setPromptsContent(content);
    return;
  }
  setters.setPrdContent(content);
}

export { mapPrdPhaseToSteps };
