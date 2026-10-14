import { StreamError } from '../services/api';
import type { PrdGenerationStage } from '../types';
import { getPrdFailureStageLabel } from './generationSteps';

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof StreamError) {
    if (error.code === 'TOKEN_BUDGET_EXCEEDED') {
      return error.message;
    }
    if (error.message.trim()) {
      return `${fallback}：${error.message}`;
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return `${fallback}：${error.message}`;
  }
  return fallback;
}

export function getErrorRequestId(error: unknown): string | null {
  if (error instanceof StreamError && error.request_id) {
    return error.request_id;
  }
  return null;
}

export function formatPrdGenerationFailure(
  stage: PrdGenerationStage,
  elapsedSeconds: number,
  error: unknown,
): string {
  if (error instanceof StreamError && error.code === 'TOKEN_BUDGET_EXCEEDED') {
    return error.message;
  }
  return `生成在「${getPrdFailureStageLabel(stage)}」阶段失败 · 已等待 ${elapsedSeconds}s`;
}
