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
  const collapsedText = `本次生成：${formatDurationMs(summary.total_duration_ms)} · ${formatTokens(totalTokens)} tokens`;

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
    <div className="flex-shrink-0 border-t border-gray-100 bg-gray-50/60">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-1.5 px-6 py-2 text-left text-xs text-gray-500 transition-colors hover:bg-gray-100/80"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gray-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-gray-400" />
        )}
        {collapsedText}
      </button>
      {expanded && (
        <div className="space-y-1 border-t border-gray-100 px-6 py-2.5 text-xs text-gray-600">
          <div className="font-medium text-gray-700">本次生成统计</div>
          <div>· 总耗时 {formatDurationMs(summary.total_duration_ms)}</div>
          <div>
            · 约 {totalTokens.toLocaleString()} tokens（输入约{' '}
            {formatTokens(summary.total_input_tokens)} / 输出约{' '}
            {formatTokens(summary.total_output_tokens)}）
          </div>
          <div>· LLM 调用 {summary.llm_call_count ?? '—'} 次</div>
          {summary.revision_applied != null && (
            <div>
              · 审查：{summary.revision_applied ? '1 轮修订' : '无需修订'}
            </div>
          )}
          {summary.injected_skills && summary.injected_skills.length > 0 && (
            <div className="space-y-1">
              {summary.injected_skills.map((skill) => (
                <details key={skill.skill_id} className="group">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                    参考规范：{skill.skill_id}
                    {' · '}{skill.artifacts.length} 个文件
                  </summary>
                  <ul className="ml-3 mt-1 list-disc pl-3 text-gray-500">
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
              <span>· 请求 ID：{summary.request_id}</span>
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-0.5 text-xs text-gray-600 hover:bg-white"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-green-600" />
                ) : (
                  <Copy className="h-3 w-3" />
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
