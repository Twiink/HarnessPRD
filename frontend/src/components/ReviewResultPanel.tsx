import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { PrdReviewResult } from '../types';
import {
  buildReviewCollapsedSummary,
  getMeaningfulReviewIssues,
  getReviewPanelSubtitle,
  getReviewStatusBadge,
} from '../utils/prdReviewDisplay';

const SEVERITY_LABELS: Record<string, string> = { high: '高', medium: '中', low: '低' };

type ReviewResultPanelProps = {
  review: PrdReviewResult | null | undefined;
  versionLabel?: string;
  defaultCollapsed?: boolean;
  revisionApplied?: boolean;
  className?: string;
};

export default function ReviewResultPanel({
  review,
  versionLabel,
  defaultCollapsed = true,
  revisionApplied = false,
  className = '',
}: ReviewResultPanelProps) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);

  if (!review) return null;

  const meaningfulIssues = getMeaningfulReviewIssues(review);
  const collapsedText = buildReviewCollapsedSummary(review, revisionApplied);
  const title = versionLabel ? `${versionLabel} 审查意见` : '审查意见';
  const statusBadge = getReviewStatusBadge(review, revisionApplied);
  const subtitle = getReviewPanelSubtitle(revisionApplied);

  return (
    <div className={`flex flex-col border-t-[1.5px] border-ink bg-sheet ${className}`}>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full flex-shrink-0 items-start gap-1.5 px-4 py-2.5 text-left transition-colors hover:bg-slate-50"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[13px] font-semibold text-ink">{title}</span>
            <span
              className={`shrink-0 rounded-sm px-1.5 text-[11px] font-medium leading-[18px] ${statusBadge.className}`}
            >
              {statusBadge.label}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{subtitle}</p>
          {!expanded && (
            <p className="mt-0.5 text-xs text-slate-600">{collapsedText}</p>
          )}
        </div>
      </button>

      {expanded && (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-hair px-4 py-3">
          {revisionApplied && (
            <div className="mb-3 rounded border border-primary-200 bg-primary-50 px-3 py-2 text-xs leading-relaxed text-primary-900">
              PRD 已按下列意见自动修订过一次。这些问题针对修订前的初稿，当前正文可能已经解决，请通读后判断。
            </div>
          )}

          {review.summary && (
            <p className="text-xs leading-relaxed text-slate-700">{review.summary}</p>
          )}

          {meaningfulIssues.length > 0 && (
            <div className="mt-2">
              {revisionApplied && (
                <p className="mb-1 text-xs text-slate-500">
                  修订前问题
                </p>
              )}
              {meaningfulIssues.map((issue, index) => (
                <div
                  key={`${issue.section}-${index}`}
                  className="grid grid-cols-[26px_1fr] gap-2 border-b border-dashed border-hair py-2.5 last:border-b-0"
                >
                  <span
                    className={`mt-0.5 grid h-[22px] w-[22px] place-items-center rounded-full border-[1.5px] font-cond text-xs font-semibold ${
                      issue.severity === 'high'
                        ? 'border-mark text-mark'
                        : issue.severity === 'medium'
                          ? 'border-stamp text-stamp'
                          : 'border-slate-400 text-slate-500'
                    }`}
                    title={SEVERITY_LABELS[issue.severity] ?? issue.severity}
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-2 text-[11px] text-slate-500">
                      <span className="font-medium">{SEVERITY_LABELS[issue.severity] ?? issue.severity}</span>
                      <span>{issue.section}</span>
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink">{issue.problem}</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">建议：{issue.suggestion}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
