import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import {
  deleteSession,
  listSessions,
  type SessionSummary,
} from '../services/sessionService';
import BrandMark from './BrandMark';

const ENTRY_MODE_LABELS: Record<string, string> = {
  structured: '从零整理',
  prd: '导入 PRD',
  prompts: '导入 PRD + 接口文档',
};

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export default function SessionList() {
  const navigate = useNavigate();
  const [items, setItems] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    const list = await listSessions();
    setItems(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const handleDelete = async (id: string, title: string) => {
    if (!window.confirm(`确定删除方案「${title}」？删除后无法恢复。`)) return;
    setDeletingId(id);
    const ok = await deleteSession(id);
    setDeletingId(null);
    if (ok) {
      setItems((prev) => prev.filter((item) => item.id !== id));
    }
  };

  return (
    <div className="min-h-screen bg-ground">
      <header className="flex h-[52px] items-center justify-between border-b-[1.5px] border-ink bg-sheet px-5 text-ink lg:px-7">
        <button type="button" onClick={() => navigate('/')} className="rounded" aria-label="返回工作台">
          <BrandMark />
        </button>
        <button type="button" onClick={() => navigate('/')} className="btn-primary">
          <Plus className="h-4 w-4" aria-hidden />
          新建方案
        </button>
      </header>

      <main className="mx-auto w-full max-w-6xl px-5 py-10 lg:px-8">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-ink">我的方案</h1>
            <p className="mt-1 text-sm text-slate-600">方案在工作过程中自动保存。</p>
          </div>
          {!loading && items.length > 0 && (
            <span className="font-cond text-sm font-medium text-slate-500">共 {items.length} 份</span>
          )}
        </div>

        <div className="sheet">
          {loading ? (
            <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-slate-600">
              <Loader2 className="h-4 w-4 animate-spin text-primary-600" aria-hidden />
              正在加载
            </div>
          ) : items.length === 0 ? (
            <div className="px-6 py-16 lg:px-10">
              <p className="text-base font-semibold text-ink">还没有方案</p>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-600">
                在工作台开始整理需求或导入文档后，方案会出现在这里。
              </p>
              <button type="button" onClick={() => navigate('/')} className="btn-primary mt-6">
                新建方案
              </button>
            </div>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b-[1.5px] border-ink text-left text-xs text-slate-500">
                  <th scope="col" className="px-6 py-3 font-medium">方案</th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">起点</th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">当前阶段</th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">更新时间</th>
                  <th scope="col" className="px-6 py-3 text-right font-medium">
                    <span className="sr-only">操作</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="group border-b border-hair last:border-b-0 hover:bg-primary-50/50">
                    <td className="px-6 py-4">
                      <button
                        type="button"
                        onClick={() => navigate(`/projects/${item.id}`)}
                        className="text-left text-[15px] font-semibold text-ink hover:text-primary-700 hover:underline"
                      >
                        {item.title}
                      </button>
                      <div className="mt-0.5 text-xs text-slate-500 md:hidden">
                        {item.current_stage || '未开始'}，{formatDateTime(item.updated_at)}
                      </div>
                    </td>
                    <td className="hidden px-4 py-4 text-slate-600 md:table-cell">
                      {ENTRY_MODE_LABELS[item.entry_mode || ''] || item.entry_mode || '未知'}
                    </td>
                    <td className="hidden px-4 py-4 md:table-cell">
                      <span className="text-ink">{item.current_stage || '未开始'}</span>
                      {item.status && <span className="ml-2 text-xs text-slate-500">{item.status}</span>}
                    </td>
                    <td className="hidden px-4 py-4 tabular-nums text-slate-600 lg:table-cell">
                      {formatDateTime(item.updated_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => navigate(`/projects/${item.id}`)}
                          className="btn-outline py-1.5"
                        >
                          继续
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(item.id, item.title)}
                          disabled={deletingId === item.id}
                          className="btn-quiet px-2 py-1.5 hover:text-mark"
                          aria-label={`删除方案 ${item.title}`}
                          title="删除"
                        >
                          {deletingId === item.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                          ) : (
                            <Trash2 className="h-4 w-4" aria-hidden />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
