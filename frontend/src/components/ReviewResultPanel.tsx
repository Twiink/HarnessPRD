import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { PrdReviewResult } from '../types';
import {
  buildReviewCollapsedSummary,
  getMeaningfulReviewIssues,
  getReviewPanelSubtitle,
  getReviewStatusBadge,
} from '../utils/prdReviewDisplay';

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
            <span className="text-xs font-medium text-gray-700">{title}</span>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${statusBadge.className}`}
            >
              {statusBadge.label}
            </span>
          </div>
          <p className="mt-0.5 text-[10px] leading-relaxed text-gray-400">{subtitle}</p>
          {!expanded && (
            <p className="mt-0.5 text-xs text-gray-500">{collapsedText}</p>
          )}
        </div>
      </button>

      {expanded && (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-gray-100 px-4 py-3">
          {revisionApplied && (
            <div className="mb-3 rounded-md border border-sky-100 bg-sky-50 px-3 py-2 text-[11px] leading-relaxed text-sky-900">
              系统已根据下列意见自动修订 PRD。这些问题针对修订前初稿，当前正文可能已部分或全部解决，请通读正文后自行判断。
            </div>
          )}

          {review.summary && (
            <p className="text-xs leading-relaxed text-gray-600">{review.summary}</p>
          )}

          {meaningfulIssues.length > 0 && (
            <div className="mt-2 space-y-2">
              {revisionApplied && (
                <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                  修订前问题
                </p>
              )}
              {meaningfulIssues.map((issue, index) => (
                <div
                  key={`${issue.section}-${index}`}
                  className="rounded-md border border-gray-100 bg-gray-50 p-2.5"
                >
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        issue.severity === 'high'
                          ? 'bg-red-100 text-red-700'
                          : issue.severity === 'medium'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {issue.severity.toUpperCase()}
                    </span>
                    <span className="text-[10px] text-gray-500">{issue.section}</span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-gray-800">{issue.problem}</p>
                  <p className="mt-1 text-xs leading-relaxed text-gray-500">
                    建议：{issue.suggestion}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
