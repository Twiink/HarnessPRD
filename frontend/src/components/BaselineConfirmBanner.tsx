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

export default function BaselineConfirmBanner({
  confirmed,
  confirmedAt,
  highIssueCount = 0,
  revisionApplied = false,
  onConfirm,
  confirmDisabled,
}: BaselineConfirmBannerProps) {
  if (confirmed) {
    const timeLabel = confirmedAt ? ` · ${formatConfirmedAt(confirmedAt)}` : '';
    return (
      <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        已确认需求基线
        {timeLabel}
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <p className="font-medium">需求基线尚未确认</p>
      <p className="mt-1 text-amber-900/90">
        {revisionApplied
          ? 'PRD 已按审查意见自动修订，请通读当前正文。确认后将解锁接口文档与提示词生成。'
          : '请通读 PRD。确认后将解锁接口文档与提示词生成。'}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onConfirm}
          disabled={confirmDisabled}
        >
          确认需求基线
        </button>
        {highIssueCount > 0 && (
          <span className="text-xs text-amber-800">
            仍有 {highIssueCount} 个审查问题，确认即表示接受风险
          </span>
        )}
      </div>
    </div>
  );
}

export { countHighReviewIssuesForBaseline };

export function countHighReviewIssues(review: PrdReviewResult | null | undefined): number {
  return countHighReviewIssuesForBaseline(review, false);
}
