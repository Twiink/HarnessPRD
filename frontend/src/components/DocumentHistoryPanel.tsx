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
    <div className="flex max-h-[30%] w-full shrink-0 flex-col border-t border-hair bg-sheet lg:h-full lg:max-h-none lg:w-80 lg:border-l-[1.5px] lg:border-t-0 lg:border-l-ink">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b-[1.5px] border-ink px-4 py-2.5">
        <h3 className="text-[13px] font-semibold text-ink">版本记录</h3>
        {hasVersions && !isGenerating && (
          <button
            type="button"
            onClick={() => void onCheckpoint()}
            disabled={isCheckpointing || isLoadingPreview}
            className="btn-outline px-2.5 py-1 text-xs"
          >
            {isCheckpointing ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            保存快照
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {error && (
          <div className="m-3 rounded border border-mark/30 bg-red-50 px-3 py-2 text-xs text-mark">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => void onRetry()}
              className="mt-1 inline-flex items-center gap-1 font-medium underline-offset-2 hover:underline"
            >
              <RefreshCw className="h-3 w-3" />
              重试
            </button>
          </div>
        )}

        {isLoading && versions.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载
          </div>
        ) : !hasVersions ? (
          <p className="px-4 py-8 text-sm text-slate-500">还没有版本。文档生成或编辑后会自动记录。</p>
        ) : (
          <ul
            className={`${versionPanelLocked ? 'pointer-events-none opacity-90' : ''}`}
            aria-disabled={versionPanelLocked || undefined}
          >
            {generatingVersionNo != null && (
              <li
                className={`border-b border-hair ${
                  isGeneratingNewVersion ? 'bg-primary-50' : 'opacity-70'
                }`}
              >
                <div className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 flex-shrink-0 rounded-full ${
                        isGeneratingNewVersion
                          ? 'animate-pulse bg-primary-600'
                          : 'animate-pulse bg-slate-400'
                      }`}
                    />
                    <span className="font-cond text-[15px] font-semibold text-ink">v{generatingVersionNo}</span>
                    <span
                      className={`rounded-sm border px-1.5 text-[11px] font-medium leading-[18px] ${
                        isGeneratingNewVersion
                          ? 'border-primary-600 text-primary-700'
                          : 'border-slate-300 text-slate-500'
                      }`}
                    >
                      {isGeneratingNewVersion ? '生成中' : '待生成'}
                    </span>
                  </div>
                  <div className="mt-1 pl-4 text-xs text-slate-500">
                    {isGeneratingNewVersion ? '正文区显示实时内容' : '生成完成后可查看和编辑'}
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
                  className={`border-b border-hair transition-colors ${
                    isPreviewing
                      ? 'bg-amber-50'
                      : isCurrent
                        ? 'bg-primary-50/70'
                        : versionPanelLocked
                          ? ''
                          : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-start gap-1 px-4 py-2.5">
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
                            isCurrent ? 'bg-primary-600' : 'bg-slate-300'
                          }`}
                        />
                        <span className="font-cond text-[15px] font-semibold text-ink">v{version.version_no}</span>
                        {isCurrent && (
                          <span className="rounded-sm border border-primary-600 px-1.5 text-[11px] font-medium leading-[18px] text-primary-700">
                            当前
                          </span>
                        )}
                        {isPreviewing && !isCurrent && (
                          <span className="rounded-sm border border-stamp px-1.5 text-[11px] font-medium leading-[18px] text-stamp">
                            查看中
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 flex items-center justify-between gap-2 pl-4 text-xs text-slate-500">
                        <span>{sourceLabel}</span>
                        <span className="tabular-nums">{formatDocumentHistoryTime(version.created_at)}</span>
                      </div>
                      {savedNote && !isEditingNote && (
                        <p className="mt-1 line-clamp-2 pl-4 text-xs leading-relaxed text-slate-700">
                          {savedNote}
                        </p>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => openNoteEditor(version)}
                      disabled={isSavingNote || versionPanelLocked}
                      className={`mt-0.5 flex-shrink-0 rounded px-1.5 py-0.5 text-xs transition-colors hover:bg-slate-100 hover:text-ink disabled:opacity-50 ${
                        savedNote ? 'text-primary-700' : 'text-slate-500'
                      }`}
                    >
                      备注
                    </button>
                  </div>

                  {isEditingNote && (
                    <div className="px-4 pb-3">
                      <textarea
                        value={draftNote}
                        onChange={(event) => setDraftNote(event.target.value)}
                        placeholder="补充记录说明，例如定稿前备份"
                        rows={2}
                        maxLength={200}
                        disabled={isSavingNote}
                        aria-label="版本备注"
                        className="w-full resize-none rounded border border-slate-300 bg-white px-2.5 py-2 text-xs text-ink placeholder:text-slate-400 focus:border-primary-600 focus:outline-none focus:ring-1 focus:ring-primary-600 disabled:opacity-60"
                      />
                      <div className="mt-2 flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={closeNoteEditor}
                          disabled={isSavingNote}
                          className="btn-quiet px-2 py-1 text-xs"
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveNote(version.id)}
                          disabled={isSavingNote}
                          className="btn-primary px-2 py-1 text-xs"
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
          <div className="flex items-center gap-2 px-4 py-2 text-xs text-slate-500">
            <Loader2 className="h-3 w-3 animate-spin" />
            正在载入版本
          </div>
        )}
      </div>

      {showReviewPanel && (
        <div className="flex max-h-[42%] min-h-0 flex-shrink-0 flex-col">
          {isLoadingReview ? (
            <div className="flex items-center gap-2 border-t border-hair px-4 py-3 text-xs text-slate-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              {reviewVersionLabel ? `正在载入 ${reviewVersionLabel} 的审查意见` : '正在载入审查意见'}
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
        <div className="flex-shrink-0 border-t border-hair px-4 py-2 text-xs text-slate-500">
          {isGeneratingNewVersion
            ? '正在生成新版本'
            : '当前工作稿'}
        </div>
      )}
    </div>
  );
}
