import type { SummaryDiffItem } from '../types/summaryDiff';

interface SummaryDiffPanelProps {
  items: SummaryDiffItem[];
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  confirming?: boolean;
}

function diffTypeLabel(changeType: SummaryDiffItem['changeType']): string {
  if (changeType === 'added') return '新增';
  if (changeType === 'removed') return '删除';
  return '修改';
}

function diffTypeClass(changeType: SummaryDiffItem['changeType']): string {
  if (changeType === 'added') return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  if (changeType === 'removed') return 'bg-rose-100 text-rose-700 border-rose-200';
  return 'bg-amber-100 text-amber-700 border-amber-200';
}

export default function SummaryDiffPanel({
  items,
  loading = false,
  onConfirm,
  onCancel,
  confirming = false,
}: SummaryDiffPanelProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col py-6">
      <div className="flex-shrink-0">
        <h2 className="text-lg font-semibold text-slate-900">生成 PRD 前 · 确认结构化摘要变更</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          系统已根据<strong className="font-medium text-slate-800">澄清对话</strong>
          对照当前表单摘要做了比对。下方仅列出有变化的字段；确认后会把这些更新写入结构化摘要，并据此生成 PRD。
        </p>
      </div>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full min-h-[12rem] items-center justify-center rounded-xl border border-slate-200 bg-white p-8">
            <div className="text-center">
              <div className="text-sm font-medium text-slate-800">正在分析澄清对话并比对摘要…</div>
              <p className="mt-2 text-sm text-slate-500">请耐心等待</p>
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <div className="text-sm font-medium text-slate-800">未发现需要确认的字段差异</div>
            <p className="mt-2 text-sm text-slate-600">可直接继续生成 PRD。</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">共 {items.length} 项变更，请逐项核对：</p>
            {items.map((item, index) => (
              <div
                key={item.path}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-medium text-white">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-slate-900">{item.path}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${diffTypeClass(item.changeType)}`}
                      >
                        {diffTypeLabel(item.changeType)}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-2">
                      <div>
                        <div className="mb-1 text-xs font-medium text-slate-500">回填前</div>
                        <pre className="max-h-40 overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-700">
                          {item.before}
                        </pre>
                      </div>
                      <div>
                        <div className="mb-1 text-xs font-medium text-slate-500">回填后</div>
                        <pre className="max-h-40 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                          {item.after}
                        </pre>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {!loading && (
        <div className="mt-6 flex flex-shrink-0 flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={confirming}
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            返回澄清对话
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirming || items.length === 0}
            className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {confirming ? '生成中…' : '确认并生成 PRD'}
          </button>
        </div>
      )}
    </div>
  );
}
