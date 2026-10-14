import type { StepItem } from '../components/GenerationStepper';
import type { PrdGenerationStage, RunSummary } from '../types';

export const PRD_STEP_DEFS = [
  { id: 'writer', label: '起草 PRD' },
  { id: 'review', label: '机器审查' },
  { id: 'rewrite', label: '修订 PRD' },
];

export const API_DOCS_STEP_DEFS = [
  { id: 'generate', label: '生成接口文档' },
  { id: 'review', label: '机器审查' },
];

export const PROMPTS_STEP_DEFS = [
  { id: 'generate', label: '生成提示词套件' },
  { id: 'review', label: '机器审查' },
];

export const REVIEW_STEP_HINT = '正在对照需求审查文档，通常需要 10–30 秒…';

export function mapPrdPhaseToSteps(phase: string): StepItem[] {
  if (phase === 'review_started') {
    return [
      { ...PRD_STEP_DEFS[0], status: 'done' },
      { ...PRD_STEP_DEFS[1], status: 'active' },
      { ...PRD_STEP_DEFS[2], status: 'pending' },
    ];
  }
  if (phase === 'rewrite_started') {
    return [
      { ...PRD_STEP_DEFS[0], status: 'done' },
      { ...PRD_STEP_DEFS[1], status: 'done' },
      { ...PRD_STEP_DEFS[2], status: 'active' },
    ];
  }
  return [
    { ...PRD_STEP_DEFS[0], status: 'active' },
    { ...PRD_STEP_DEFS[1], status: 'pending' },
    { ...PRD_STEP_DEFS[2], status: 'pending' },
  ];
}

export function finalizePrdStepsFromSummary(summary: RunSummary): StepItem[] {
  if (summary.revision_applied) {
    return PRD_STEP_DEFS.map((step) => ({ ...step, status: 'done' as const }));
  }
  return [
    { ...PRD_STEP_DEFS[0], status: 'done' },
    { ...PRD_STEP_DEFS[1], status: 'done' },
    { ...PRD_STEP_DEFS[2], status: 'pending' },
  ];
}

export function createApiDocsGeneratingSteps(): StepItem[] {
  return [
    { ...API_DOCS_STEP_DEFS[0], status: 'active' },
    { ...API_DOCS_STEP_DEFS[1], status: 'pending' },
  ];
}

export function mapApiDocsPhaseToSteps(phase: string): StepItem[] {
  if (phase === 'review_started') {
    return [
      { ...API_DOCS_STEP_DEFS[0], status: 'done' },
      { ...API_DOCS_STEP_DEFS[1], status: 'active' },
    ];
  }
  return createApiDocsGeneratingSteps();
}

export function markApiDocsStepsDone(): StepItem[] {
  return API_DOCS_STEP_DEFS.map((step) => ({ ...step, status: 'done' as const }));
}

export function createPromptsGeneratingSteps(): StepItem[] {
  return [
    { ...PROMPTS_STEP_DEFS[0], status: 'active' },
    { ...PROMPTS_STEP_DEFS[1], status: 'pending' },
  ];
}

export function mapPromptsPhaseToSteps(phase: string): StepItem[] {
  if (phase === 'review_started') {
    return [
      { ...PROMPTS_STEP_DEFS[0], status: 'done' },
      { ...PROMPTS_STEP_DEFS[1], status: 'active' },
    ];
  }
  return createPromptsGeneratingSteps();
}

export function markPromptsStepsDone(): StepItem[] {
  return PROMPTS_STEP_DEFS.map((step) => ({ ...step, status: 'done' as const }));
}

export function getPrdFailureStageLabel(stage: PrdGenerationStage): string {
  if (stage === 'reviewing') return '机器审查';
  if (stage === 'rewriting') return '修订 PRD';
  return '起草 PRD';
}
