import type {
  ClarificationRoundUsage,
  ContextUsage,
  PrdGenerationStage,
  PrdReviewResult,
  RunSummary,
} from '../types';
import type { StepItem } from '../components/GenerationStepper';
import type { StreamHandlers } from '../services/api';
import { StreamError } from '../services/api';
import {
  createApiDocsGeneratingSteps,
  createPromptsGeneratingSteps,
  finalizePrdStepsFromSummary,
  mapPrdPhaseToSteps,
  mapApiDocsPhaseToSteps,
  mapPromptsPhaseToSteps,
  markApiDocsStepsDone,
  markPromptsStepsDone,
  REVIEW_STEP_HINT,
} from '../utils/generationSteps';
import {
  formatPrdGenerationFailure,
  getErrorMessage,
  getErrorRequestId,
} from '../utils/streamErrors';
import { useCallback, useEffect, useRef, useState } from 'react';

type CaptureStreamErrorOptions = {
  kind?: 'generic' | 'prd';
  fallback?: string;
  getStageRef?: () => PrdGenerationStage;
};

export type GenerationArtifact = 'prd' | 'api-docs' | 'prompts';

type RunSummariesByArtifact = Partial<Record<GenerationArtifact, RunSummary>>;

export function useGenerationObservability() {
  const [runSummaries, setRunSummaries] = useState<RunSummariesByArtifact>({});
  const [contextUsage, setContextUsage] = useState<ContextUsage | null>(null);
  const [clarificationRounds, setClarificationRounds] = useState<ClarificationRoundUsage[]>([]);
  const pendingClarificationUsageRef = useRef<ContextUsage | null>(null);
  const [generationSteps, setGenerationSteps] = useState<StepItem[]>([]);
  const [generationElapsed, setGenerationElapsed] = useState(0);
  const [generationHint, setGenerationHint] = useState<string | undefined>();
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);

  const timerRef = useRef<number | null>(null);
  const generationElapsedRef = useRef(0);

  useEffect(() => {
    generationElapsedRef.current = generationElapsed;
  }, [generationElapsed]);

  const stopTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    stopTimer();
    setGenerationElapsed(0);
    generationElapsedRef.current = 0;
    timerRef.current = window.setInterval(() => {
      setGenerationElapsed((value) => {
        const next = value + 1;
        generationElapsedRef.current = next;
        return next;
      });
    }, 1000);
  }, [stopTimer]);

  const resetGenerationState = useCallback(() => {
    setGenerationSteps([]);
    setGenerationHint(undefined);
    setGenerationElapsed(0);
    generationElapsedRef.current = 0;
  }, []);

  const clearRunSummaryForArtifact = useCallback((artifact: GenerationArtifact) => {
    setRunSummaries((prev) => {
      if (!(artifact in prev)) return prev;
      const next = { ...prev };
      delete next[artifact];
      return next;
    });
  }, []);

  const resetGeneration = useCallback(() => {
    resetGenerationState();
    setRunSummaries({});
  }, [resetGenerationState]);

  const resetErrorMeta = useCallback(() => {
    setErrorRequestId(null);
  }, []);

  const clearSteps = useCallback(() => {
    setGenerationSteps([]);
    setGenerationHint(undefined);
  }, []);

  const resetClarificationRounds = useCallback(() => {
    setClarificationRounds([]);
    setContextUsage(null);
    pendingClarificationUsageRef.current = null;
  }, []);

  const handleContextUsage = useCallback((usage: ContextUsage) => {
    setContextUsage(usage);
  }, []);

  const handleClarificationContextUsage = useCallback((usage: ContextUsage) => {
    setContextUsage(usage);
    pendingClarificationUsageRef.current = usage;
  }, []);

  const handleClarificationRunSummary = useCallback((summary: RunSummary) => {
    const usage = pendingClarificationUsageRef.current;
    if (!usage) return;
    pendingClarificationUsageRef.current = null;
    setClarificationRounds((prev) => {
      const round = prev.length + 1;
      return [
        ...prev,
        {
          round,
          label: round === 1 ? '首轮' : `第 ${round} 轮`,
          usage,
          durationMs: summary.total_duration_ms,
          outputTokens: summary.total_output_tokens,
        },
      ];
    });
  }, []);

  const createClarificationHandlers = useCallback(
    (): Pick<StreamHandlers, 'onContextUsage' | 'onRunSummary'> => ({
      onContextUsage: handleClarificationContextUsage,
      onRunSummary: handleClarificationRunSummary,
    }),
    [handleClarificationContextUsage, handleClarificationRunSummary],
  );

  const handleRunSummary = useCallback(
    (
      summary: RunSummary,
      options?: {
        artifact?: GenerationArtifact;
        finalizeSteps?: (summary: RunSummary) => StepItem[];
      },
    ) => {
      if (options?.artifact) {
        setRunSummaries((prev) => ({ ...prev, [options.artifact!]: summary }));
      }
      if (options?.finalizeSteps) {
        setGenerationSteps(options.finalizeSteps(summary));
        setGenerationHint(undefined);
      }
      stopTimer();
    },
    [stopTimer],
  );

  const getRunSummary = useCallback(
    (artifact: GenerationArtifact) => runSummaries[artifact] ?? null,
    [runSummaries],
  );

  const beginApiDocsGeneration = useCallback(() => {
    resetGenerationState();
    clearRunSummaryForArtifact('api-docs');
    resetErrorMeta();
    setGenerationSteps(createApiDocsGeneratingSteps());
    startTimer();
  }, [clearRunSummaryForArtifact, resetErrorMeta, resetGenerationState, startTimer]);

  const beginPromptsGeneration = useCallback(() => {
    resetGenerationState();
    clearRunSummaryForArtifact('prompts');
    resetErrorMeta();
    setGenerationSteps(createPromptsGeneratingSteps());
    startTimer();
  }, [clearRunSummaryForArtifact, resetErrorMeta, resetGenerationState, startTimer]);

  const beginPrdGeneration = useCallback(() => {
    resetGenerationState();
    clearRunSummaryForArtifact('prd');
    resetErrorMeta();
    setGenerationSteps(mapPrdPhaseToSteps('writer_started'));
    startTimer();
  }, [clearRunSummaryForArtifact, resetErrorMeta, resetGenerationState, startTimer]);

  const createChunkJobHandlers = useCallback(
    (artifact: 'api-docs' | 'prompts'): StreamHandlers => {
      const mapPhase = artifact === 'api-docs' ? mapApiDocsPhaseToSteps : mapPromptsPhaseToSteps;
      const finalizeSteps = artifact === 'api-docs' ? markApiDocsStepsDone : markPromptsStepsDone;
      return {
        onPhase: (phase) => {
          setGenerationSteps(mapPhase(phase));
          if (phase === 'review_started') {
            setGenerationHint(REVIEW_STEP_HINT);
          } else {
            setGenerationHint(undefined);
          }
        },
        onRunSummary: (summary) => {
          handleRunSummary(summary, {
            artifact,
            finalizeSteps: () => finalizeSteps(),
          });
        },
      };
    },
    [handleRunSummary],
  );

  const createApiDocsHandlers = useCallback((): StreamHandlers => {
    return createChunkJobHandlers('api-docs');
  }, [createChunkJobHandlers]);

  const createPromptsHandlers = useCallback((): StreamHandlers => {
    return createChunkJobHandlers('prompts');
  }, [createChunkJobHandlers]);

  const createPrdHandlers = useCallback(
    (options?: {
      onPhase?: (phase: string) => void;
      onReview?: (review: PrdReviewResult) => void;
    }): StreamHandlers => {
      return {
        onPhase: (phase) => {
          setGenerationSteps(mapPrdPhaseToSteps(phase));
          if (phase === 'review_started') {
            setGenerationHint(REVIEW_STEP_HINT);
          } else if (phase !== 'rewrite_started') {
            setGenerationHint(undefined);
          }
          options?.onPhase?.(phase);
        },
        onReview: options?.onReview,
        onRunSummary: (summary) => {
          handleRunSummary(summary, {
            artifact: 'prd',
            finalizeSteps: finalizePrdStepsFromSummary,
          });
        },
      };
    },
    [handleRunSummary],
  );

  const captureStreamError = useCallback(
    (error: unknown, options?: CaptureStreamErrorOptions) => {
      const requestId = getErrorRequestId(error);
      setErrorRequestId(requestId);

      let message: string;
      if (options?.kind === 'prd') {
        if (error instanceof StreamError && error.code === 'TOKEN_BUDGET_EXCEEDED') {
          message = error.message;
        } else {
          message = formatPrdGenerationFailure(
            options.getStageRef?.() ?? 'writing',
            generationElapsedRef.current,
            error,
          );
        }
      } else {
        message = getErrorMessage(error, options?.fallback ?? '操作失败');
      }

      return { message, requestId };
    },
    [],
  );

  const copyErrorRequestId = useCallback(async () => {
    if (!errorRequestId) return;
    try {
      await navigator.clipboard.writeText(errorRequestId);
    } catch {
      /* ignore */
    }
  }, [errorRequestId]);

  useEffect(() => () => stopTimer(), [stopTimer]);

  return {
    runSummaries,
    getRunSummary,
    contextUsage,
    clarificationRounds,
    generationSteps,
    generationElapsed,
    generationHint,
    errorRequestId,
    resetGeneration,
    resetErrorMeta,
    startTimer,
    stopTimer,
    clearSteps,
    beginApiDocsGeneration,
    beginPromptsGeneration,
    beginPrdGeneration,
    handleContextUsage,
    handleClarificationContextUsage,
    handleClarificationRunSummary,
    createClarificationHandlers,
    resetClarificationRounds,
    handleRunSummary,
    createApiDocsHandlers,
    createPromptsHandlers,
    createPrdHandlers,
    captureStreamError,
    copyErrorRequestId,
  };
}
