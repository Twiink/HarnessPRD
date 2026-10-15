import type { PrdReviewResult, ReviewIssue } from '../types';

export function getMeaningfulReviewIssues(review: PrdReviewResult): ReviewIssue[] {
  return (review.issues ?? []).filter(
    (issue) => issue.problem?.trim() || issue.suggestion?.trim(),
  );
}

export function hasReviewDetail(review: PrdReviewResult): boolean {
  return !!(review.summary?.trim() || getMeaningfulReviewIssues(review).length);
}

export function shouldShowReviewPanel(review: PrdReviewResult | null | undefined): boolean {
  if (!review) return false;
  return hasReviewDetail(review);
}

export function countHighReviewIssues(review: PrdReviewResult | null | undefined): number {
  if (!review?.issues?.length) return 0;
  return review.issues.filter((issue) => issue.severity === 'high').length;
}

/** 自动修订后，审查意见针对初稿，不计入基线确认的风险提示 */
export function countHighReviewIssuesForBaseline(
  review: PrdReviewResult | null | undefined,
  revisionApplied: boolean,
): number {
  if (revisionApplied) return 0;
  return countHighReviewIssues(review);
}

export function resolveRevisionApplied(
  fromVersionMetadata?: boolean | null,
  fromRunSummary?: boolean | null,
): boolean {
  if (fromVersionMetadata != null) return fromVersionMetadata;
  return fromRunSummary ?? false;
}

export function getReviewPanelSubtitle(revisionApplied: boolean): string {
  if (revisionApplied) {
    return '以下意见针对自动修订前的初稿；当前正文已按意见修订，仅供参考';
  }
  return '基于生成时审查，修改后仅供参考';
}

export function getReviewStatusBadge(
  review: PrdReviewResult,
  revisionApplied: boolean,
): { label: string; className: string } {
  if (revisionApplied) {
    return {
      label: '已自动修订',
      className: 'border border-primary-600 text-primary-700',
    };
  }
  if (review.passed) {
    return {
      label: '已通过',
      className: 'border border-primary-600 text-primary-700',
    };
  }
  return {
    label: '待改进',
    className: 'border border-stamp text-stamp',
  };
}

export function buildReviewCollapsedSummary(
  review: PrdReviewResult,
  revisionApplied: boolean,
): string {
  const issueCount = getMeaningfulReviewIssues(review).length;
  if (revisionApplied) {
    if (issueCount > 0) {
      return `审查：已自动修订 · ${issueCount} 项修订前问题`;
    }
    return '审查：已自动修订';
  }
  const status = review.passed ? '已通过' : '已提出修改';
  if (issueCount > 0) {
    return `审查：${status} · ${issueCount} 项问题`;
  }
  return `审查：${status}`;
}
