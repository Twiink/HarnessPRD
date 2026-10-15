import { Loader2 } from 'lucide-react';
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
  if (changeType === 'added') return 'border-primary-600 text-primary-700';
  if (changeType === 'removed') return 'border-mark text-mark';
  return 'border-stamp text-stamp';
}

export default function SummaryDiffPanel({
  items,
  loading = false,
  onConfirm,
  onCancel,
  confirming = false,
}: SummaryDiffPanelProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col py-8">
      <div className="flex-shrink-0">
        <h2 className="text-[24px] font-semibold tracking-[-0.01em] text-ink">核对需求变更</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          这是澄清对话对需求摘要的改动。确认后写入需求，并据此生成 PRD。
        </p>
      </div>

      <div className="sheet mt-6 flex min-h-0 flex-1 flex-col">
        {loading ? (
          <div className="flex min-h-[14rem] flex-1 items-center justify-center gap-2 text-sm text-slate-600" role="status">
            <Loader2 className="h-4 w-4 animate-spin text-primary-600" aria-hidden />
            正在比对澄清对话和需求摘要
          </div>
        ) : items.length === 0 ? (
          <div className="px-6 py-10">
            <div className="text-sm font-semibold text-ink">没有需要核对的改动</div>
            <p className="mt-1 text-sm text-slate-600">可以直接生成 PRD。</p>
          </div>
        ) : (
          <>
            <div className="grid flex-shrink-0 grid-cols-[48px_minmax(0,1fr)] border-b-[1.5px] border-ink text-xs text-slate-500 lg:grid-cols-[48px_minmax(0,14rem)_minmax(0,1fr)_minmax(0,1fr)]">
              <div className="px-3 py-2.5">序号</div>
              <div className="px-3 py-2.5">字段</div>
              <div className="hidden border-l border-hair px-3 py-2.5 lg:block">原内容</div>
              <div className="hidden border-l border-hair px-3 py-2.5 lg:block">新内容</div>
            </div>
            <ol className="min-h-0 flex-1 overflow-y-auto">
              {items.map((item, index) => (
                <li
                  key={item.path}
                  className="grid grid-cols-[48px_minmax(0,1fr)] border-b border-hair last:border-b-0 lg:grid-cols-[48px_minmax(0,14rem)_minmax(0,1fr)_minmax(0,1fr)]"
                >
                  <div className="px-3 py-3 font-cond text-[15px] font-semibold text-primary-600">{index + 1}</div>
                  <div className="px-3 py-3">
                    <div className="break-words text-sm font-medium text-ink">{item.path}</div>
                    <span
                      className={`mt-1 inline-block rounded-sm border px-1.5 text-[11px] font-medium leading-[18px] ${diffTypeClass(item.changeType)}`}
                    >
                      {diffTypeLabel(item.changeType)}
                    </span>
                  </div>
                  <div className="col-start-2 border-hair px-3 pb-2 lg:col-start-auto lg:border-l lg:py-3">
                    <div className="mb-1 text-xs text-slate-500 lg:hidden">原内容</div>
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-sans text-xs leading-5 text-slate-500 line-through decoration-slate-300">
                      {item.before || '（空）'}
                    </pre>
                  </div>
                  <div className="col-start-2 border-hair px-3 pb-3 lg:col-start-auto lg:border-l lg:py-3">
                    <div className="mb-1 text-xs text-slate-500 lg:hidden">新内容</div>
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-sans text-xs leading-5 text-ink">
                      {item.after || '（空）'}
                    </pre>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>

      {!loading && (
        <div className="mt-5 flex flex-shrink-0 flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-slate-600">{items.length > 0 ? `共 ${items.length} 处改动` : ''}</span>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={onCancel} disabled={confirming} className="btn-outline">
              返回澄清对话
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={confirming || items.length === 0}
              className="btn-primary"
            >
              {confirming ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
              确认改动并生成 PRD
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
