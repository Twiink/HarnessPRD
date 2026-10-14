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
        className="absolute inset-0 bg-slate-900/45 backdrop-blur-[2px]"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="clarification-confirm-title"
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-amber-200/80 bg-white shadow-2xl shadow-slate-900/10"
      >
        <div className="border-b border-amber-100 bg-gradient-to-b from-amber-50 to-white px-6 py-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0 pt-0.5">
              <h2 id="clarification-confirm-title" className="text-base font-semibold text-slate-900">
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
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">待确认问题</div>
              <ul className="mt-2 space-y-2">
                {state.openQuestions.map((question) => (
                  <li
                    key={question}
                    className="flex gap-2 rounded-lg border border-amber-100 bg-amber-50/60 px-3 py-2.5 text-sm leading-relaxed text-amber-950"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" aria-hidden />
                    <span>{question}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hasWarnings && (
            <div className={hasQuestions ? 'mt-4' : ''}>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">提示</div>
              <ul className="mt-2 space-y-2">
                {state.warnings.map((warning) => (
                  <li
                    key={warning}
                    className="flex gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-700"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" aria-hidden />
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50/80 px-6 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            返回继续澄清
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-xl border border-amber-400 bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-amber-700"
          >
            仍要生成 PRD
          </button>
        </div>
      </div>
    </div>
  );
}
