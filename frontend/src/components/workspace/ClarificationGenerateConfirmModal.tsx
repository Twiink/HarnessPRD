import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { ClarificationState } from '../../types/clarificationState';

type ClarificationGenerateConfirmModalProps = {
  open: boolean;
  state: ClarificationState;
  onCancel: () => void;
  onConfirm: () => void;
};

export default function ClarificationGenerateConfirmModal({
  open,
  state,
  onCancel,
  onConfirm,
}: ClarificationGenerateConfirmModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  const hasQuestions = state.openQuestions.length > 0;
  const hasWarnings = state.warnings.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="关闭"
        className="absolute inset-0 bg-ink/50"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="clarification-confirm-title"
        className="sheet relative w-full max-w-lg overflow-hidden shadow-xl"
      >
        <div className="border-b-[1.5px] border-ink px-6 py-5">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-[1.5px] border-stamp text-stamp">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 pt-0.5">
              <h2 id="clarification-confirm-title" className="text-[17px] font-semibold text-ink">
                仍有未澄清的需求点
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                现在生成 PRD 可能产生较多「待确认」或 Review 问题。
              </p>
            </div>
          </div>
        </div>

        <div className="max-h-[min(50vh,20rem)] overflow-y-auto px-6 py-5">
          {hasQuestions && (
            <div>
              <div className="text-xs text-slate-500">还没回答的问题</div>
              <ul className="mt-1.5">
                {state.openQuestions.map((question) => (
                  <li
                    key={question}
                    className="flex gap-2 border-b border-dashed border-hair py-2 text-sm leading-relaxed text-ink last:border-b-0"
                  >
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-stamp" aria-hidden />
                    <span>{question}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hasWarnings && (
            <div className={hasQuestions ? 'mt-4' : ''}>
              <div className="text-xs text-slate-500">提示</div>
              <ul className="mt-1.5">
                {state.warnings.map((warning) => (
                  <li
                    key={warning}
                    className="flex gap-2 border-b border-dashed border-hair py-2 text-sm leading-relaxed text-slate-700 last:border-b-0"
                  >
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" aria-hidden />
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-hair px-6 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="btn-outline"
          >
            返回继续澄清
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="btn-primary"
          >
            仍要生成 PRD
          </button>
        </div>
      </div>
    </div>
  );
}
