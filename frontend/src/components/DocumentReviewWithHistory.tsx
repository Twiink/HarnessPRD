import { useEffect, useMemo, useRef, useState } from 'react';
import DocumentReview, { type DocumentReviewProps } from './DocumentReview';
import DocumentHistoryPanel from './DocumentHistoryPanel';
import StaleArtifactBanner from './StaleArtifactBanner';
import { useDocumentVersions } from '../hooks/useDocumentVersions';
import { fetchVersionList } from '../services/documentApi';
import { formatDocumentHistoryTime, resolveCurrentVersionNo } from '../utils/documentVersions';
import type { DocumentType } from '../types/document';
import type { PrdReviewResult } from '../types';
import type { QualityGateResult } from '../types/qualityGate';
import { buildStaleWarnings } from '../utils/staleArtifact';
import { resolveRevisionApplied } from '../utils/prdReviewDisplay';

export type DocumentReviewBannerContext = {
  revisionApplied: boolean;
  displayReview: PrdReviewResult | null;
};

function resolveVersionReview(
  detail: ReturnType<typeof useDocumentVersions>['activeDetail'],
  sessionReview?: PrdReviewResult | null,
): PrdReviewResult | null {
  const fromMeta = detail?.metadata?.review ?? null;
  if (fromMeta) return fromMeta;
  if (
    detail &&
    detail.version_no === 1 &&
    detail.source_kind !== 'checkpoint' &&
    detail.source_kind !== 'restore' &&
    sessionReview
  ) {
    return sessionReview;
  }
  return null;
}

export type DocumentReviewWithHistoryProps = {
  sessionId: string | undefined;
  docType: DocumentType;
  content: string;
  onContentChange: (content: string) => void;
  jobIdle: boolean;
  reviewResult?: PrdReviewResult | null;
  headerBanner?: React.ReactNode | ((ctx: DocumentReviewBannerContext) => React.ReactNode);
  onRegenerateStale?: () => void;
} & Omit<
  DocumentReviewProps,
  | 'content'
  | 'onSaveEdit'
  | 'versionPanel'
  | 'isPreviewMode'
  | 'previewLabel'
  | 'onRestorePreview'
  | 'isRestoring'
  | 'reviewResult'
  | 'qualityGate'
>;

export default function DocumentReviewWithHistory({
  sessionId,
  docType,
  content,
  onContentChange,
  jobIdle,
  reviewResult,
  headerBanner,
  onRegenerateStale,
  ...reviewProps
}: DocumentReviewWithHistoryProps) {
  const versions = useDocumentVersions({
    sessionId,
    docType,
    editorContent: content,
    enabled: !!sessionId,
  });

  const prevJobIdle = useRef(jobIdle);
  useEffect(() => {
    if (!prevJobIdle.current && jobIdle) {
      void versions.refreshList();
    }
    prevJobIdle.current = jobIdle;
  }, [jobIdle, versions.refreshList]);

  const isGeneratingNow = !!(reviewProps.isGeneratingPhase || reviewProps.isGenerating);

  useEffect(() => {
    if (isGeneratingNow && versions.preview) {
      versions.closePreview();
    }
  }, [isGeneratingNow, versions.preview, versions.closePreview]);

  const generatingVersionNo = useMemo(() => {
    if (!isGeneratingNow) return null;
    if (versions.versions.length === 0) return 1;
    const maxNo = Math.max(...versions.versions.map((v) => v.version_no));
    return maxNo + 1;
  }, [isGeneratingNow, versions.versions]);

  const isPreviewMode = !!versions.preview;
  const previewLabel = versions.preview ? formatDocumentHistoryTime(versions.preview.created_at) : undefined;
  // 审查意见优先读历史记录 metadata；初始记录缺少 metadata 时用 session 回填。
  const displayReview = resolveVersionReview(versions.activeDetail, reviewResult);
  const revisionApplied = resolveRevisionApplied(
    versions.activeDetail?.metadata?.run_summary?.revision_applied,
    reviewProps.runSummary?.revision_applied,
  );
  const displayQualityGate: QualityGateResult | null =
    versions.activeDetail?.metadata?.quality_gate ?? null;

  const renderedHeaderBanner =
    typeof headerBanner === 'function'
      ? headerBanner({ revisionApplied, displayReview })
      : headerBanner;

  const [prdCurrentVersionNo, setPrdCurrentVersionNo] = useState<number | null>(null);
  const [apiDocsCurrentVersionNo, setApiDocsCurrentVersionNo] = useState<number | null>(null);

  useEffect(() => {
    if (!sessionId || docType === 'prd') return;
    void fetchVersionList(sessionId, 'prd').then((result) => {
      setPrdCurrentVersionNo(resolveCurrentVersionNo(result));
    });
  }, [sessionId, docType, versions.currentVersionNo]);

  useEffect(() => {
    if (!sessionId || docType !== 'prompts') return;
    void fetchVersionList(sessionId, 'api-docs').then((result) => {
      setApiDocsCurrentVersionNo(resolveCurrentVersionNo(result));
    });
  }, [sessionId, docType, versions.currentVersionNo]);

  const staleWarnings = useMemo(() => {
    if (docType === 'prd') return [];
    return buildStaleWarnings({
      docType,
      derivedFrom: versions.activeDetail?.metadata?.derived_from,
      prdCurrentVersionNo,
      apiDocsCurrentVersionNo,
      onRegenerate: onRegenerateStale,
    });
  }, [
    docType,
    versions.activeDetail?.metadata?.derived_from,
    prdCurrentVersionNo,
    apiDocsCurrentVersionNo,
    onRegenerateStale,
  ]);

  const handleRestorePreview = async () => {
    try {
      const restoredContent = await versions.restorePreview();
      if (restoredContent != null) {
        onContentChange(restoredContent);
      }
    } catch {
      /* error shown in version panel */
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {(renderedHeaderBanner || staleWarnings.length > 0) && (
        <div className="shrink-0 space-y-3 border-b border-hair bg-sheet px-6 py-3 lg:px-8">
          {renderedHeaderBanner}
          <StaleArtifactBanner warnings={staleWarnings} />
        </div>
      )}
      <DocumentReview
        {...reviewProps}
        reviewResult={displayReview}
        revisionApplied={revisionApplied}
        qualityGate={displayQualityGate}
        content={isGeneratingNow ? content : (versions.preview?.content ?? content)}
        isPreviewMode={!isGeneratingNow && isPreviewMode}
        previewLabel={previewLabel}
        onRestorePreview={() => void handleRestorePreview()}
        isRestoring={versions.isRestoring}
        onSaveEdit={(value) => {
          if (versions.preview) return;
          onContentChange(value);
        }}
        versionPanel={
          <DocumentHistoryPanel
            versions={versions.versions}
            currentVersionNo={versions.currentVersionNo}
            previewVersionId={versions.previewVersionId}
            isLoading={versions.isLoadingList}
            isLoadingPreview={versions.isLoadingPreview}
            isLoadingReview={
              (versions.isLoadingPreview || versions.isLoadingCurrentDetail) && !displayReview
            }
            error={versions.error}
            isCheckpointing={versions.isCheckpointing}
            savingNoteVersionId={versions.savingNoteVersionId}
            showReview
            review={displayReview}
            reviewVersionLabel={versions.activeVersionLabel}
            revisionApplied={revisionApplied}
            onSelectVersion={versions.openPreview}
            onCheckpoint={() => void versions.checkpoint()}
            onSaveVersionNote={(versionId, changeNote) =>
              void versions.saveVersionNote(versionId, changeNote)
            }
            onRetry={versions.refreshList}
            generatingVersionNo={generatingVersionNo}
            isGenerating={isGeneratingNow}
          />
        }
      />
    </div>
  );
}
