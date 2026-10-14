import type { SummaryDiffItem } from '../types/summaryDiff';

function normalizeDiffValue(value: unknown): string {
  if (value === undefined || value === null) return '未设置';
  if (typeof value === 'string') return value || '未设置';
  return JSON.stringify(value, null, 2);
}

export function collectSummaryDiff(before: unknown, after: unknown, path = ''): SummaryDiffItem[] {
  if (JSON.stringify(before) === JSON.stringify(after)) {
    return [];
  }

  const beforeIsObject = typeof before === 'object' && before !== null && !Array.isArray(before);
  const afterIsObject = typeof after === 'object' && after !== null && !Array.isArray(after);

  if (beforeIsObject && afterIsObject) {
    const keys = Array.from(new Set([
      ...Object.keys(before as Record<string, unknown>),
      ...Object.keys(after as Record<string, unknown>),
    ])).sort();

    return keys.flatMap((key) =>
      collectSummaryDiff(
        (before as Record<string, unknown>)[key],
        (after as Record<string, unknown>)[key],
        path ? `${path}.${key}` : key,
      ),
    );
  }

  let changeType: SummaryDiffItem['changeType'] = 'modified';
  if (before === undefined || before === null || before === '') {
    changeType = 'added';
  } else if (after === undefined || after === null || after === '') {
    changeType = 'removed';
  }

  return [{
    path: path || 'root',
    changeType,
    before: normalizeDiffValue(before),
    after: normalizeDiffValue(after),
  }];
}
