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
  if (level === 'warn') return 'text-amber-700 bg-amber-50';
  if (level === 'exceed') return 'text-red-700 bg-red-50';
  return 'text-slate-600 bg-slate-100';
}

export default function ClarificationContextPanel({
  rounds,
  defaultCollapsed = true,
}: ClarificationContextPanelProps) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);

  if (rounds.length === 0) return null;

  const latest = rounds[rounds.length - 1];
  const collapsedText = `澄清 context：${rounds.length} 轮 · 最新约 ${formatTokens(latest.usage.estimated_input_tokens)} / ${formatTokens(latest.usage.budget_tokens)}`;

  return (
    <div className="mb-3 flex-shrink-0 rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
        )}
        {collapsedText}
      </button>
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="space-y-2">
            {rounds.map((round) => (
              <div
                key={round.round}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600"
              >
                <span className="font-medium text-slate-800">{round.label}</span>
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
                  className={`rounded px-1.5 py-0.5 text-xs ${levelClass(round.usage.level)}`}
                >
                  {levelLabel(round.usage.level)}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-400">
            输入为发送前估算；每轮独立统计，含 system 与截至该轮的全部对话。
          </p>
        </div>
      )}
    </div>
  );
}
