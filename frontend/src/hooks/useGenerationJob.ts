import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocType, Message, PrdGenerationStage, PrdReviewResult } from '../types';
import type { GeneratePrdStreamResult } from '../types';
import type { JobArtifact, JobSnapshot } from '../types/job';
import type { RequirementsSummary, WorkspaceViewState } from '../services/sessionService';
import { createJob, getJob } from '../services/jobApi';
import { readJobStream } from '../utils/jobStream';
import {
  contentArtifactFromJob,
  finalizeStepsForArtifact,
  generatingViewFor,
  isOptimizeArtifact,
  jobPhaseToSsePhase,
  optimizeArtifactFor,
  reviewViewFor,
  setContentForArtifact,
} from '../utils/jobViews';
import type { useGenerationObservability } from './useGenerationObservability';
import { getErrorMessage } from '../utils/streamErrors';

type SessionLoadState = 'idle' | 'loading' | 'ready' | 'not_found' | 'error';

type ContentSetters = {
  setPrdContent: (v: string) => void;
  setApiDocsContent: (v: string) => void;
  setPromptsContent: (v: string) => void;
};

export type UseGenerationJobOptions = {
  sessionId: string | undefined;
  sessionLoadState: SessionLoadState;
  activeJobId: string | null | undefined;
  messages: Message[];
  obs: ReturnType<typeof useGenerationObservability>;
  setContent: ContentSetters;
  setViewState: (v: WorkspaceViewState) => void;
  setPrdReviewResult: (v: PrdReviewResult | null) => void;
  setStreamingContent: (v: string) => void;
  setError: (v: string) => void;
  setActiveJobId: (v: string | null | undefined) => void;
  setPrdGenerationStage: (v: PrdGenerationStage) => void;
  prdGenerationStageRef: React.MutableRefObject<PrdGenerationStage>;
  onInvalidateBaseline?: () => void;
};

function messagesForPayload(messages: Message[]) {
  return messages.map((m) => ({
    role: m.role === 'ai' ? 'assistant' : m.role,
    content: m.content,
  }));
}

export function useGenerationJob(options: UseGenerationJobOptions) {
  const {
    sessionId,
    sessionLoadState,
    activeJobId,
    messages,
    obs,
    setContent,
    setViewState,
    setPrdReviewResult,
    setStreamingContent,
    setError,
    setActiveJobId,
    setPrdGenerationStage,
    prdGenerationStageRef,
    onInvalidateBaseline,
  } = options;

  const [isJobRunning, setIsJobRunning] = useState(false);
  const [isOptimizingJob, setIsOptimizingJob] = useState(false);
  const streamAbortRef = useRef<AbortController | null>(null);
  const reconnectStartedRef = useRef(false);
  const subscribeInFlightRef = useRef(false);

  const subscribeJob = useCallback(
    async (jobId: string, artifact: JobArtifact) => {
      if (subscribeInFlightRef.current) return;
      subscribeInFlightRef.current = true;
      setIsJobRunning(true);

      streamAbortRef.current?.abort();
      const ac = new AbortController();
      streamAbortRef.current = ac;

      let accumulated = '';
      const contentArtifact = contentArtifactFromJob(artifact);
      const isOptimize = isOptimizeArtifact(artifact);
      const isPrdGenerate = artifact === 'prd';
      const isChunkGenerate = artifact === 'api-docs' || artifact === 'prompts';

      if (!isOptimize) {
        if (isPrdGenerate) {
          obs.beginPrdGeneration();
        } else if (artifact === 'api-docs') {
          obs.beginApiDocsGeneration();
        } else {
          obs.beginPromptsGeneration();
        }
      }

      const prdHandlers = isPrdGenerate
        ? obs.createPrdHandlers({
            onPhase: (phase) => {
              if (phase === 'writer_started') {
                if (!accumulated) {
                  setPrdGenerationStage('writing');
                  setStreamingContent('');
                }
              } else if (phase === 'review_started') {
                setPrdGenerationStage('reviewing');
                setStreamingContent('');
              } else if (phase === 'rewrite_started') {
                const initialDraft = accumulated;
                accumulated = '';
                setPrdGenerationStage('rewriting');
                setStreamingContent('');
                if (initialDraft) {
                  setContentForArtifact(artifact, initialDraft, setContent);
                }
              }
            },
            onReview: (review) => setPrdReviewResult(review),
          })
        : null;

      const chunkHandlers = isChunkGenerate
        ? artifact === 'api-docs'
          ? obs.createApiDocsHandlers()
          : obs.createPromptsHandlers()
        : null;

      const syncSnapshotPhase = (phase: import('../types/job').JobPhase) => {
        if (!isPrdGenerate) return;
        const ssePhase = jobPhaseToSsePhase(phase);
        if (ssePhase) {
          prdHandlers?.onPhase?.(ssePhase);
        }
      };

      try {
        const result = await readJobStream(
          jobId,
          {
            onSnapshot: (snap) => {
              accumulated = snap.draft_content || '';
              setContentForArtifact(contentArtifact, accumulated, setContent);
              setStreamingContent('');
              if (isPrdGenerate) {
                if (snap.phase === 'writing') setPrdGenerationStage('writing');
                if (snap.phase === 'reviewing') setPrdGenerationStage('reviewing');
                if (snap.phase === 'rewriting') setPrdGenerationStage('rewriting');
                syncSnapshotPhase(snap.phase);
              } else if (isChunkGenerate && snap.phase === 'reviewing') {
                chunkHandlers?.onPhase?.('review_started');
              }
              if (snap.review) setPrdReviewResult(snap.review);
            },
            onPhase: (phase) => {
              prdHandlers?.onPhase?.(phase);
              chunkHandlers?.onPhase?.(phase);
              if (isChunkGenerate && phase === 'review_started') {
                setStreamingContent('');
              }
            },
            onReview: (review) => {
              prdHandlers?.onReview?.(review);
            },
            onChunk: (chunk) => {
              accumulated += chunk;
              setContentForArtifact(contentArtifact, accumulated, setContent);
              setStreamingContent(accumulated);
            },
            onRunSummary: (summary) => {
              obs.handleRunSummary(summary, {
                artifact: contentArtifact,
                finalizeSteps: isOptimize
                  ? undefined
                  : (s) => finalizeStepsForArtifact(contentArtifact, s),
              });
            },
          },
          ac.signal,
        );

        if (isPrdGenerate && result && typeof result === 'object' && 'final_prd' in (result as object)) {
          const prdResult = result as GeneratePrdStreamResult;
          accumulated = prdResult.final_prd;
          setContentForArtifact(contentArtifact, accumulated, setContent);
          setPrdReviewResult(prdResult.review);
          setPrdGenerationStage('done');
          onInvalidateBaseline?.();
        } else if (result && typeof result === 'object' && 'content' in (result as object)) {
          const content = (result as { content?: string }).content || accumulated;
          accumulated = content;
          setContentForArtifact(contentArtifact, content, setContent);
        }

        setActiveJobId(null);
        setViewState(reviewViewFor(artifact));
        setStreamingContent('');
        if (isOptimize) {
          setIsOptimizingJob(false);
          if (contentArtifact === 'prd') {
            onInvalidateBaseline?.();
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        console.error(err);
        if (isOptimize) {
          setError(getErrorMessage(err, '优化文档失败'));
          obs.stopTimer();
        } else if (artifact === 'prd') {
          const { message } = obs.captureStreamError(err, {
            kind: 'prd',
            getStageRef: () => prdGenerationStageRef.current,
          });
          setError(message);
          setPrdGenerationStage('error');
        } else {
          setError(getErrorMessage(err, '生成失败'));
          obs.clearSteps();
          obs.stopTimer();
        }
        if (accumulated) {
          setContentForArtifact(contentArtifact, accumulated, setContent);
        }
        setActiveJobId(null);
        setViewState(reviewViewFor(artifact));
        if (isOptimize) {
          setIsOptimizingJob(false);
        }
      } finally {
        subscribeInFlightRef.current = false;
        setIsJobRunning(false);
        setStreamingContent('');
        if (isOptimizeArtifact(artifact)) {
          setIsOptimizingJob(false);
        }
      }
    },
    [
      obs,
      setContent,
      setViewState,
      setPrdReviewResult,
      setStreamingContent,
      setError,
      setActiveJobId,
      setPrdGenerationStage,
      prdGenerationStageRef,
      onInvalidateBaseline,
    ],
  );

  const applyCompletedJob = useCallback(
    (job: JobSnapshot) => {
      const contentArtifact = contentArtifactFromJob(job.artifact);
      const draft = job.draft_content || '';
      setContentForArtifact(contentArtifact, draft, setContent);
      if (isOptimizeArtifact(job.artifact)) {
        setActiveJobId(null);
        setViewState(reviewViewFor(job.artifact));
        setStreamingContent('');
        setIsOptimizingJob(false);
        obs.stopTimer();
        return;
      }
      if (job.artifact === 'prd') {
        if (job.review) setPrdReviewResult(job.review);
        const result = job.result as GeneratePrdStreamResult | null;
        if (result?.final_prd) {
          setContent.setPrdContent(result.final_prd);
        }
        setPrdGenerationStage('done');
        onInvalidateBaseline?.();
      }
      setActiveJobId(null);
      setViewState(reviewViewFor(job.artifact));
      setStreamingContent('');
      obs.clearSteps();
      obs.stopTimer();
    },
    [obs, setContent, setViewState, setPrdReviewResult, setStreamingContent, setActiveJobId, setPrdGenerationStage],
  );

  const applyFailedJob = useCallback(
    (job: JobSnapshot) => {
      const contentArtifact = contentArtifactFromJob(job.artifact);
      if (job.draft_content) {
        setContentForArtifact(contentArtifact, job.draft_content, setContent);
      }
      setError(job.error || (isOptimizeArtifact(job.artifact) ? '优化已中断' : '生成已中断'));
      setActiveJobId(null);
      setViewState(reviewViewFor(job.artifact));
      if (isOptimizeArtifact(job.artifact)) {
        setIsOptimizingJob(false);
        obs.stopTimer();
        return;
      }
      obs.clearSteps();
      obs.stopTimer();
    },
    [obs, setContent, setViewState, setError, setActiveJobId],
  );

  useEffect(() => {
    reconnectStartedRef.current = false;
  }, [sessionId]);

  useEffect(() => {
    if (sessionLoadState !== 'ready' || !sessionId || !activeJobId) return;
    if (reconnectStartedRef.current || subscribeInFlightRef.current) return;

    let cancelled = false;

    void (async () => {
      try {
        const job = await getJob(activeJobId);
        if (cancelled) return;

        if (job.status === 'running') {
          reconnectStartedRef.current = true;
          if (isOptimizeArtifact(job.artifact)) {
            setIsOptimizingJob(true);
            const contentArtifact = contentArtifactFromJob(job.artifact);
            setViewState(reviewViewFor(job.artifact));
            setContentForArtifact(contentArtifact, job.draft_content || '', setContent);
            setStreamingContent('');
            await subscribeJob(activeJobId, job.artifact);
            return;
          }
          setViewState(generatingViewFor(job.artifact));
          setContentForArtifact(job.artifact, job.draft_content || '', setContent);
          setStreamingContent('');
          if (job.review) setPrdReviewResult(job.review);
          await subscribeJob(activeJobId, job.artifact);
          return;
        }

        if (job.status === 'completed') {
          applyCompletedJob(job);
          return;
        }

        if (job.status === 'failed') {
          applyFailedJob(job);
        }
      } catch (err) {
        if (!cancelled) {
          console.error(err);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    sessionLoadState,
    sessionId,
    activeJobId,
    subscribeJob,
    applyCompletedJob,
    applyFailedJob,
    setViewState,
    setContent,
    setStreamingContent,
    setPrdReviewResult,
  ]);

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
  }, []);

  const startPrd = useCallback(
    async (summary: RequirementsSummary, targetSessionId?: string) => {
      const sid = targetSessionId ?? sessionId;
      if (!sid) return;
      reconnectStartedRef.current = true;
      setError('');
      setContent.setPrdContent('');
      setPrdReviewResult(null);
      setStreamingContent('');
      setViewState('generating-prd');
      setPrdGenerationStage('writing');

      try {
        const { job_id } = await createJob(sid, 'prd', {
          requirements_summary: summary,
          conversation_messages: messagesForPayload(messages),
        });
        setActiveJobId(job_id);
        await subscribeJob(job_id, 'prd');
      } catch (err) {
        reconnectStartedRef.current = false;
        console.error(err);
        const { message } = obs.captureStreamError(err, {
          kind: 'prd',
          getStageRef: () => prdGenerationStageRef.current,
        });
        setError(message);
        setPrdGenerationStage('error');
        setViewState('review-prd');
        obs.clearSteps();
        obs.stopTimer();
      }
    },
    [
      sessionId,
      messages,
      setError,
      setContent,
      setPrdReviewResult,
      setStreamingContent,
      setViewState,
      setPrdGenerationStage,
      setActiveJobId,
      subscribeJob,
    ],
  );

  const startApiDocs = useCallback(
    async (prd: string, targetSessionId?: string) => {
      const sid = targetSessionId ?? sessionId;
      if (!sid) return;
      reconnectStartedRef.current = true;
      setError('');
      setContent.setApiDocsContent('');
      setStreamingContent('');
      setViewState('generating-api-docs');

      try {
        const { job_id } = await createJob(sid, 'api-docs', {
          prd_content: prd,
          conversation_messages: messagesForPayload(messages),
        });
        setActiveJobId(job_id);
        await subscribeJob(job_id, 'api-docs');
      } catch (err) {
        reconnectStartedRef.current = false;
        console.error(err);
        const { message } = obs.captureStreamError(err, { fallback: '生成接口文档失败' });
        setError(message);
        setViewState('review-prd');
        obs.clearSteps();
        obs.stopTimer();
      }
    },
    [sessionId, messages, setError, setContent, setStreamingContent, setViewState, setActiveJobId, subscribeJob],
  );

  const startPrompts = useCallback(
    async (prd: string, apiDocs: string, targetSessionId?: string) => {
      const sid = targetSessionId ?? sessionId;
      if (!sid) return;
      reconnectStartedRef.current = true;
      setError('');
      setContent.setPromptsContent('');
      setStreamingContent('');
      setViewState('generating-prompts');

      try {
        const { job_id } = await createJob(sid, 'prompts', {
          prd_content: prd,
          api_docs_content: apiDocs,
          conversation_messages: messagesForPayload(messages),
        });
        setActiveJobId(job_id);
        await subscribeJob(job_id, 'prompts');
      } catch (err) {
        reconnectStartedRef.current = false;
        console.error(err);
        const { message } = obs.captureStreamError(err, { fallback: '生成提示词失败' });
        setError(message);
        setViewState(apiDocs.trim() ? 'review-api-docs' : 'review-prd');
        obs.clearSteps();
        obs.stopTimer();
      }
    },
    [sessionId, messages, setError, setContent, setStreamingContent, setViewState, setActiveJobId, subscribeJob],
  );

  const startOptimize = useCallback(
    async (docType: DocType, currentContent: string, instruction: string, context: string) => {
      if (!sessionId) return;
      const artifact = optimizeArtifactFor(docType);
      reconnectStartedRef.current = true;
      setError('');
      setIsOptimizingJob(true);
      setStreamingContent('');

      try {
        const { job_id } = await createJob(sessionId, artifact, {
          doc_type: docType,
          current_content: currentContent,
          instruction,
          context,
        });
        setActiveJobId(job_id);
        await subscribeJob(job_id, artifact);
      } catch (err) {
        reconnectStartedRef.current = false;
        console.error(err);
        setError(getErrorMessage(err, '优化文档失败'));
        setIsOptimizingJob(false);
        setActiveJobId(null);
      }
    },
    [sessionId, setError, setStreamingContent, setActiveJobId, subscribeJob],
  );

  return {
    startPrd,
    startApiDocs,
    startPrompts,
    startOptimize,
    isJobRunning,
    isOptimizingJob,
  };
}
