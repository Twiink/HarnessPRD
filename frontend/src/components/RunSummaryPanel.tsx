import { useState } from 'react';
import { Check, ChevronDown, ChevronRight, Copy } from 'lucide-react';
import type { RunSummary } from '../types';

export function formatTokens(n?: number): string {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1000) return `约 ${Math.round(n / 1000)}k`;
  return String(n);
}

export function formatDurationMs(ms?: number): string {
  if (ms == null || Number.isNaN(ms)) return '—';
  return `${Math.round(ms / 1000)}s`;
}

type RunSummaryPanelProps = {
  summary: RunSummary | null;
  defaultCollapsed?: boolean;
};

export default function RunSummaryPanel({
  summary,
  defaultCollapsed = true,
}: RunSummaryPanelProps) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);
  const [copied, setCopied] = useState(false);

  if (!summary) return null;

  const totalTokens =
    (summary.total_input_tokens ?? 0) + (summary.total_output_tokens ?? 0);
  const collapsedText = `本次生成用时 ${formatDurationMs(summary.total_duration_ms)}，${formatTokens(totalTokens)} tokens`;

  const handleCopy = async () => {
    if (!summary.request_id) return;
    try {
      await navigator.clipboard.writeText(summary.request_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="flex-shrink-0 border-t border-hair">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-1.5 px-6 py-2 text-left text-xs text-slate-500 transition-colors hover:bg-slate-50 hover:text-ink lg:px-8"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
        )}
        {collapsedText}
      </button>
      {expanded && (
        <div className="space-y-1 border-t border-hair px-6 py-2.5 text-xs tabular-nums text-slate-600 lg:px-8">
          <div className="font-medium text-ink">本次生成统计</div>
          <div>总耗时 {formatDurationMs(summary.total_duration_ms)}</div>
          <div>
            共约 {totalTokens.toLocaleString()} tokens（输入约{' '}
            {formatTokens(summary.total_input_tokens)} / 输出约{' '}
            {formatTokens(summary.total_output_tokens)}）
          </div>
          <div>模型调用 {summary.llm_call_count ?? '—'} 次</div>
          {summary.revision_applied != null && (
            <div>
              审查：{summary.revision_applied ? '修订 1 轮' : '无需修订'}
            </div>
          )}
          {summary.injected_skills && summary.injected_skills.length > 0 && (
            <div className="space-y-1">
              {summary.injected_skills.map((skill) => (
                <details key={skill.skill_id} className="group">
                  <summary className="cursor-pointer text-slate-500 hover:text-ink">
                    参考规范：{skill.skill_id}
                    ，{skill.artifacts.length} 个文件
                  </summary>
                  <ul className="ml-3 mt-1 list-disc pl-3 text-slate-500">
                    {skill.artifacts.map((path) => (
                      <li key={path}>{path.split('/').pop()}</li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          )}
          {summary.request_id && (
            <div className="flex flex-wrap items-center gap-2">
              <span>请求 ID：<span className="font-mono">{summary.request_id}</span></span>
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="btn-quiet px-2 py-0.5 text-xs"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-primary-600" aria-hidden />
                ) : (
                  <Copy className="h-3 w-3" aria-hidden />
                )}
                复制
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
