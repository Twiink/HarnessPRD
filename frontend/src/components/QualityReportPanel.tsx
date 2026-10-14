import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { QualityGateResult } from '../types/qualityGate';

type QualityReportPanelProps = {
  qualityGate: QualityGateResult | null | undefined;
  defaultCollapsed?: boolean;
  className?: string;
};

function buildCollapsedSummary(gate: QualityGateResult): string {
  const failedHigh = gate.checks.filter((c) => !c.passed && c.severity === 'high').length;
  if (failedHigh > 0) {
    return `质量报告：${gate.score} 分 · ${failedHigh} 项未通过`;
  }
  return `质量报告：${gate.score} 分 · 结构检查通过`;
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
    <div className={`flex flex-col border-t border-gray-200 bg-white ${className}`}>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full flex-shrink-0 items-start gap-1.5 px-4 py-2.5 text-left transition-colors hover:bg-gray-50"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-gray-700">质量报告</span>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                qualityGate.passed ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
              }`}
            >
              {qualityGate.score} 分
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-gray-400">格式与结构规则检查（非模型语义审查）</p>
          {!expanded && <p className="mt-0.5 text-xs text-gray-500">{collapsedText}</p>}
        </div>
      </button>

      {expanded && (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-gray-100 px-4 py-3">
          <ul className="space-y-2">
            {qualityGate.checks.map((check) => (
              <li key={check.id} className="flex items-start gap-2 text-xs">
                <span className="mt-0.5 shrink-0">
                  {check.passed ? (
                    <span className="text-emerald-600">✓</span>
                  ) : (
                    <span className="text-red-600">✕</span>
                  )}
                </span>
                <div>
                  <div className="font-medium text-gray-800">{check.label}</div>
                  {!check.passed && check.detail && (
                    <div className="mt-0.5 text-gray-600">{check.detail}</div>
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
