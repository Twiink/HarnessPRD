import { useState } from 'react';
import { Check, ChevronDown, ChevronRight, X } from 'lucide-react';
import type { QualityGateResult } from '../types/qualityGate';

type QualityReportPanelProps = {
  qualityGate: QualityGateResult | null | undefined;
  defaultCollapsed?: boolean;
  className?: string;
};

function buildCollapsedSummary(gate: QualityGateResult): string {
  const failedHigh = gate.checks.filter((c) => !c.passed && c.severity === 'high').length;
  if (failedHigh > 0) {
    return `${gate.score} 分，${failedHigh} 项未通过`;
  }
  return `${gate.score} 分，结构检查全部通过`;
}

export default function QualityReportPanel({
  qualityGate,
  defaultCollapsed = true,
  className = '',
}: QualityReportPanelProps) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);

  if (!qualityGate) return null;

  const collapsedText = buildCollapsedSummary(qualityGate);

  return (
    <div className={`flex flex-col border-t border-hair bg-sheet ${className}`}>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full flex-shrink-0 items-start gap-1.5 px-6 py-2.5 text-left transition-colors hover:bg-slate-50 lg:px-8"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold text-ink">结构检查</span>
            <span
              className={`shrink-0 rounded-sm border px-1.5 font-cond text-xs font-semibold leading-[18px] ${
                qualityGate.passed ? 'border-primary-600 text-primary-700' : 'border-stamp text-stamp'
              }`}
            >
              {qualityGate.score} 分
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-500">按格式规则检查文档结构，不评价内容</p>
          {!expanded && <p className="mt-0.5 text-xs text-slate-600">{collapsedText}</p>}
        </div>
      </button>

      {expanded && (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-hair px-6 py-3 lg:px-8">
          <ul className="space-y-2">
            {qualityGate.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-2 text-xs">
                <span className="mt-0.5 shrink-0">
                  {check.passed ? (
                    <Check className="h-3.5 w-3.5 text-primary-600" aria-label="通过" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-mark" aria-label="未通过" />
                  )}
                </span>
                <div>
                  <div className="font-medium text-ink">{check.label}</div>
                  {!check.passed && check.detail && (
                    <div className="mt-0.5 text-slate-600">{check.detail}</div>
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
