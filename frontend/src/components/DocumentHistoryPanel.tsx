import { useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import type { PrdReviewResult } from '../types';
import type { DocumentVersionListItem, DocumentVersionSourceKind } from '../types/document';
import ReviewResultPanel from './ReviewResultPanel';
import { shouldShowReviewPanel } from '../utils/prdReviewDisplay';
import { formatDocumentHistoryTime } from '../utils/documentVersions';

const SOURCE_LABELS: Record<DocumentVersionSourceKind, string> = {
  generate: '生成',
  optimize: '优化',
  auto_save: '编辑',
  checkpoint: '另存',
  restore: '恢复',
  import: '导入',
};

type DocumentHistoryPanelProps = {
  versions: DocumentVersionListItem[];
  currentVersionNo: number | null;
  previewVersionId: string | null;
  isLoading: boolean;
  isLoadingPreview: boolean;
  isLoadingReview?: boolean;
  error: string | null;
  isCheckpointing: boolean;
  savingNoteVersionId: string | null;
  review?: PrdReviewResult | null;
  reviewVersionLabel?: string | null;
  revisionApplied?: boolean;
  showReview?: boolean;
  onSelectVersion: (versionId: string) => void;
  onCheckpoint: () => void;
  onSaveVersionNote: (versionId: string, changeNote: string) => void | Promise<void>;
  onRetry: () => void;
  generatingVersionNo?: number | null;
  isGenerating?: boolean;
};

export default function DocumentHistoryPanel({
  versions,
  currentVersionNo,
  previewVersionId,
  isLoading,
  isLoadingPreview,
  isLoadingReview = false,
  error,
  isCheckpointing,
  savingNoteVersionId,
  review,
  reviewVersionLabel,
  revisionApplied = false,
  showReview = false,
  onSelectVersion,
  onCheckpoint,
  onSaveVersionNote,
  onRetry,
  generatingVersionNo = null,
  isGenerating = false,
}: DocumentHistoryPanelProps) {
  const isGeneratingNewVersion = isGenerating && generatingVersionNo != null;
  const versionPanelLocked = isGenerating;
  const hasVersions = versions.length > 0 || generatingVersionNo != null;
  const [editingNoteVersionId, setEditingNoteVersionId] = useState<string | null>(null);
  const [draftNote, setDraftNote] = useState('');

  useEffect(() => {
    if (versionPanelLocked) {
      setEditingNoteVersionId(null);
      setDraftNote('');
    }
  }, [versionPanelLocked]);

  const openNoteEditor = (version: DocumentVersionListItem) => {
    setEditingNoteVersionId(version.id);
    setDraftNote(version.change_note ?? '');
  };

  const closeNoteEditor = () => {
    setEditingNoteVersionId(null);
    setDraftNote('');
  };

  const handleSaveNote = (versionId: string) => {
    void Promise.resolve(onSaveVersionNote(versionId, draftNote.trim())).then(() => {
      closeNoteEditor();
    });
  };

  const showReviewPanel = showReview && (isLoadingReview || shouldShowReviewPanel(review));

  return (
    <div className="flex max-h-[40%] w-full shrink-0 flex-col border-t border-gray-100 bg-gray-50/80 lg:h-full lg:max-h-none lg:w-72 lg:border-l lg:border-t-0">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-800">历史记录</h3>
        {hasVersions && !isGenerating && (
          <button
            type="button"
            onClick={() => void onCheckpoint()}
            disabled={isCheckpointing || isLoadingPreview}
            className="flex items-center gap-1 rounded-md bg-primary-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isCheckpointing ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            保存快照
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {error && (
          <div className="mb-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => void onRetry()}
              className="mt-1 inline-flex items-center gap-1 text-red-800 underline-offset-2 hover:underline"
            >
              <RefreshCw className="h-3 w-3" />
              重试
            </button>
          </div>
        )}

        {isLoading && versions.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中...
          </div>
        ) : !hasVersions ? (
          <p className="py-8 text-center text-sm text-gray-400">暂无历史记录</p>
        ) : (
          <ul
            className={`space-y-1 ${versionPanelLocked ? 'pointer-events-none opacity-90' : ''}`}
            aria-disabled={versionPanelLocked || undefined}
          >
            {generatingVersionNo != null && (
              <li
                className={`rounded-lg transition-colors ${
                  isGeneratingNewVersion
                    ? 'bg-white shadow-sm ring-1 ring-primary-200'
                    : 'bg-slate-100/90 opacity-70'
                }`}
              >
                <div className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 flex-shrink-0 rounded-full ${
                        isGeneratingNewVersion
                          ? 'animate-pulse bg-primary-500'
                          : 'animate-pulse bg-slate-400'
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-800">文档生成</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        isGeneratingNewVersion
                          ? 'bg-primary-100 text-primary-700'
                          : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      {isGeneratingNewVersion ? '生成中' : '待生成'}
                    </span>
                  </div>
                  <div className="mt-1 pl-4 text-xs text-slate-400">
                    {isGeneratingNewVersion ? '左侧为实时生成内容' : '完成后可查看与编辑'}
                  </div>
                </div>
              </li>
            )}
            {versions.map((version) => {
              const isPersistedCurrent = version.is_current;
              const isCurrent = isPersistedCurrent && !isGeneratingNewVersion;
              const isPreviewing = !versionPanelLocked && previewVersionId === version.id;
              const sourceLabel =
                SOURCE_LABELS[version.source_kind as DocumentVersionSourceKind] ?? version.source_kind;
              const isEditingNote = editingNoteVersionId === version.id;
              const isSavingNote = savingNoteVersionId === version.id;
              const savedNote = version.change_note?.trim();

              return (
                <li
                  key={version.id}
                  className={`rounded-lg transition-colors ${
                    isCurrent || isPreviewing
                      ? 'bg-white shadow-sm ring-1 ring-primary-200'
                      : versionPanelLocked
                        ? ''
                        : 'hover:bg-white/80'
                  }`}
                >
                  <div className="flex items-start gap-1 px-3 py-2.5">
                    <button
                      type="button"
                      onClick={() => void onSelectVersion(version.id)}
                      disabled={isLoadingPreview || versionPanelLocked}
                      className={`min-w-0 flex-1 text-left disabled:opacity-60 ${
                        versionPanelLocked ? 'cursor-not-allowed' : ''
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 flex-shrink-0 rounded-full ${
                            isCurrent ? 'bg-primary-500' : 'bg-gray-300'
                          }`}
                        />
                        <span className="text-sm font-medium text-gray-800">已保存文档</span>
                        {isCurrent && (
                          <span className="rounded bg-primary-100 px-1.5 py-0.5 text-[10px] font-medium text-primary-700">
                            当前
                          </span>
                        )}
                        {isPreviewing && !isCurrent && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                            预览中
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-2 pl-4 text-xs text-gray-500">
                        <span>{sourceLabel}</span>
                        <span>·</span>
                        <span>{formatDocumentHistoryTime(version.created_at)}</span>
                      </div>
                      {savedNote && !isEditingNote && (
                        <p className="mt-1.5 line-clamp-2 pl-4 text-xs leading-relaxed text-gray-600">
                          {savedNote}
                        </p>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => openNoteEditor(version)}
                      disabled={isSavingNote || versionPanelLocked}
                      className={`mt-0.5 flex-shrink-0 rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
                        savedNote
                          ? 'border-primary-300 bg-primary-50 text-primary-700 hover:bg-primary-100'
                          : 'border-gray-300 bg-white text-gray-600 hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700'
                      } disabled:opacity-50`}
                    >
                      备注
                    </button>
                  </div>

                  {isEditingNote && (
                    <div className="border-t border-gray-100 px-3 pb-3 pt-2">
                      <textarea
                        value={draftNote}
                        onChange={(event) => setDraftNote(event.target.value)}
                        placeholder="补充记录说明，例如定稿前备份"
                        rows={2}
                        maxLength={200}
                        disabled={isSavingNote}
                        className="w-full resize-none rounded-md border border-gray-200 px-2.5 py-2 text-xs text-gray-800 placeholder:text-gray-400 focus:border-primary-300 focus:outline-none focus:ring-1 focus:ring-primary-200 disabled:opacity-60"
                      />
                      <div className="mt-2 flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={closeNoteEditor}
                          disabled={isSavingNote}
                          className="rounded-md px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveNote(version.id)}
                          disabled={isSavingNote}
                          className="flex items-center gap-1 rounded-md bg-primary-600 px-2 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                        >
                          {isSavingNote ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                          保存
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {isLoadingPreview && (
          <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            加载预览...
          </div>
        )}
      </div>

      {showReviewPanel && (
        <div className="flex max-h-[42%] min-h-0 flex-shrink-0 flex-col">
          {isLoadingReview ? (
            <div className="flex items-center gap-2 border-t border-gray-200 bg-white px-4 py-3 text-xs text-gray-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              {reviewVersionLabel ? `加载 ${reviewVersionLabel} 审查意见...` : '加载审查意见...'}
            </div>
          ) : review && shouldShowReviewPanel(review) ? (
            <ReviewResultPanel
              key={reviewVersionLabel ?? 'review'}
              review={review}
              versionLabel={reviewVersionLabel ?? undefined}
              revisionApplied={revisionApplied}
              className="min-h-0"
            />
          ) : null}
        </div>
      )}

      {(currentVersionNo !== null || isGeneratingNewVersion) && !showReviewPanel && (
        <div className="flex-shrink-0 border-t border-gray-100 px-4 py-2 text-xs text-gray-400">
          {isGeneratingNewVersion
            ? '正在生成文档…'
            : '当前工作稿'}
        </div>
      )}
    </div>
  );
}
