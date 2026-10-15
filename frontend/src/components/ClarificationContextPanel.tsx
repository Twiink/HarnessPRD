import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ClarificationRoundUsage } from '../types';
import { formatDurationMs, formatTokens } from './RunSummaryPanel';

type ClarificationContextPanelProps = {
  rounds: ClarificationRoundUsage[];
  defaultCollapsed?: boolean;
};

function levelLabel(level: ClarificationRoundUsage['usage']['level']): string {
  if (level === 'warn') return '偏多';
  if (level === 'exceed') return '超限';
  return '正常';
}

function levelClass(level: ClarificationRoundUsage['usage']['level']): string {
  if (level === 'warn') return 'border-stamp text-stamp';
  if (level === 'exceed') return 'border-mark text-mark';
  return 'border-slate-300 text-slate-600';
}

export default function ClarificationContextPanel({
  rounds,
  defaultCollapsed = true,
}: ClarificationContextPanelProps) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);

  if (rounds.length === 0) return null;

  const latest = rounds[rounds.length - 1];
  const collapsedText = `上下文用量：${rounds.length} 轮，最近一轮 ${formatTokens(latest.usage.estimated_input_tokens)} / ${formatTokens(latest.usage.budget_tokens)} tokens`;

  return (
    <div className="mb-2 flex-shrink-0">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-1.5 py-1 text-left text-xs text-slate-500 hover:text-ink"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        )}
        {collapsedText}
      </button>
      {expanded && (
        <div className="mb-2 rounded border border-hair bg-white px-4 py-3">
          <div className="space-y-2">
            {rounds.map((round) => (
              <div
                key={round.round}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums text-slate-600"
              >
                <span className="font-medium text-ink">{round.label}</span>
                <span>
                  输入约 {round.usage.estimated_input_tokens.toLocaleString()} /{' '}
                  {round.usage.budget_tokens.toLocaleString()} tokens
                </span>
                {round.durationMs != null && (
                  <span>耗时 {formatDurationMs(round.durationMs)}</span>
                )}
                {round.outputTokens != null && round.outputTokens > 0 && (
                  <span>输出约 {formatTokens(round.outputTokens)}</span>
                )}
                <span
                  className={`rounded-sm border px-1.5 text-[11px] leading-[18px] ${levelClass(round.usage.level)}`}
                >
                  {levelLabel(round.usage.level)}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            输入量为发送前的估算，每轮单独统计，包含系统提示和截至该轮的全部对话。
          </p>
        </div>
      )}
    </div>
  );
}
