import { useState } from 'react';
import { AlertTriangle, Check, ChevronDown, ChevronRight, X } from 'lucide-react';
import type { ReadinessResult } from '../types/readiness';
import { readinessScoreClass, readinessStatusLabel } from '../utils/requirementsReadiness';

type ReadinessPanelProps = {
  readiness: ReadinessResult;
  onBackToForm?: () => void;
  panelRef?: React.RefObject<HTMLDivElement>;
};

export default function ReadinessPanel({ readiness, onBackToForm, panelRef }: ReadinessPanelProps) {
  const [expanded, setExpanded] = useState(readiness.blockers.length > 0);

  const collapsedText = `需求就绪度 ${readiness.score} · ${readinessStatusLabel(readiness)}`;

  return (
    <div
      ref={panelRef}
      className="mb-3 flex-shrink-0 rounded border border-hair bg-sheet"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm hover:bg-slate-50"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        )}
        <span className="text-ink">{collapsedText}</span>
        <span
          className={`ml-auto rounded-sm px-1.5 py-0.5 font-cond text-xs font-semibold ${readinessScoreClass(
            readiness.score,
            readiness.blockers.length > 0,
          )}`}
        >
          {readiness.score}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-hair px-4 py-3">
          <ul className="space-y-2">
            {readiness.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-2 text-sm">
                <span className="mt-0.5 shrink-0">
                  {check.passed ? (
                    <Check className="h-4 w-4 text-primary-600" aria-label="通过" />
                  ) : check.severity === 'blocker' ? (
                    <X className="h-4 w-4 text-mark" aria-label="必须补充" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-stamp" aria-label="建议补充" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-ink">{check.label}</div>
                  {!check.passed && check.detail && (
                    <div className="mt-0.5 text-xs text-slate-600">{check.detail}</div>
                  )}
                  {!check.passed && check.severity === 'blocker' && check.fieldHint && onBackToForm && (
                    <button
                      type="button"
                      onClick={onBackToForm}
                      className="mt-1 text-xs text-primary-700 underline hover:no-underline"
                    >
                      回到需求表补充
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
