import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
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
      className="mb-3 flex-shrink-0 rounded-lg border border-slate-200 bg-white"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm hover:bg-slate-50"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
        )}
        <span className="text-slate-700">{collapsedText}</span>
        <span
          className={`ml-auto rounded px-1.5 py-0.5 text-xs font-medium ${readinessScoreClass(
            readiness.score,
            readiness.blockers.length > 0,
          )}`}
        >
          {readiness.score}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3">
          <ul className="space-y-2">
            {readiness.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-2 text-sm">
                <span className="mt-0.5 shrink-0">
                  {check.passed ? (
                    <span className="text-emerald-600">✓</span>
                  ) : check.severity === 'blocker' ? (
                    <span className="text-red-600">✕</span>
                  ) : (
                    <span className="text-amber-600">⚠</span>
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-slate-800">{check.label}</div>
                  {!check.passed && check.detail && (
                    <div className="mt-0.5 text-xs text-slate-600">{check.detail}</div>
                  )}
                  {!check.passed && check.severity === 'blocker' && check.fieldHint && onBackToForm && (
                    <button
                      type="button"
                      onClick={onBackToForm}
                      className="mt-1 text-xs text-slate-900 underline hover:no-underline"
                    >
                      返回表单补充
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
