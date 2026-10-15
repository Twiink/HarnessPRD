import { Stamp } from 'lucide-react';
import type { PrdReviewResult } from '../types';
import { countHighReviewIssuesForBaseline } from '../utils/prdReviewDisplay';

type BaselineConfirmBannerProps = {
  confirmed: boolean;
  confirmedAt?: string | null;
  confirmedVersionNo?: number | null;
  highIssueCount?: number;
  revisionApplied?: boolean;
  onConfirm: () => void;
  confirmDisabled?: boolean;
};

function formatConfirmedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** 需求基线状态：像图纸标题栏里的审定章，已确认为蓝章，未确认为待审 */
export default function BaselineConfirmBanner({
  confirmed,
  confirmedAt,
  confirmedVersionNo,
  highIssueCount = 0,
  revisionApplied = false,
  onConfirm,
  confirmDisabled,
}: BaselineConfirmBannerProps) {
  if (confirmed) {
    return (
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="inline-flex items-center gap-1.5 rounded-sm border-[1.5px] border-primary-600 px-2 py-0.5 font-medium text-primary-700">
          <Stamp className="h-3.5 w-3.5" aria-hidden />
          需求基线已确认
        </span>
        <span className="text-slate-600">
          {confirmedVersionNo != null && <>基于 v{confirmedVersionNo}</>}
          {confirmedVersionNo != null && confirmedAt && '，'}
          {confirmedAt && <span className="tabular-nums">{formatConfirmedAt(confirmedAt)}</span>}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 shrink-0 rounded-sm border-[1.5px] border-dashed border-stamp px-2 py-0.5 text-sm font-medium text-stamp">
          基线待确认
        </span>
        <p className="max-w-2xl text-sm leading-relaxed text-slate-700">
          {revisionApplied
            ? 'PRD 已按审查意见自动修订过一次。通读当前正文，确认后即可生成接口文档和提示词。'
            : '通读 PRD，确认后即可生成接口文档和提示词。之后修改 PRD 会让基线失效。'}
          {highIssueCount > 0 && (
            <span className="ml-1 text-mark">还有 {highIssueCount} 个高优先级审查问题未处理。</span>
          )}
        </p>
      </div>
      <button type="button" className="btn-outline shrink-0" onClick={onConfirm} disabled={confirmDisabled}>
        <Stamp className="h-4 w-4" aria-hidden />
        确认为需求基线
      </button>
    </div>
  );
}

export { countHighReviewIssuesForBaseline };

export function countHighReviewIssues(review: PrdReviewResult | null | undefined): number {
  return countHighReviewIssuesForBaseline(review, false);
}
