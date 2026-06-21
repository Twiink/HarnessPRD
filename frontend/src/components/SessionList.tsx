import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Trash2, FileText, Plus } from 'lucide-react';
import {
  deleteSession,
  listSessions,
  type SessionSummary,
} from '../services/sessionService';

const V2_PAGE_CLASS = 'mx-auto w-full max-w-6xl px-6';

const ENTRY_MODE_LABELS: Record<string, string> = {
  structured: '从零开始',
  prd: '从 PRD 开始',
  prompts: '从提示词开始',
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
    if (!window.confirm(`确定删除方案「${title}」？此操作不可恢复。`)) return;
    setDeletingId(id);
    const ok = await deleteSession(id);
    setDeletingId(null);
    if (ok) {
      setItems((prev) => prev.filter((item) => item.id !== id));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className={`${V2_PAGE_CLASS} flex items-center justify-between gap-4 py-3`}>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">我的方案</div>
              <div className="text-xs text-slate-500">已保存的需求收集方案</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/v2')}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              <Plus className="h-4 w-4" />
              新建方案
            </button>
            <a href="/" className="text-sm text-slate-500 hover:text-slate-800">返回旧版</a>
          </div>
        </div>
      </header>

      <main className={`${V2_PAGE_CLASS} py-8`}>
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
            加载中…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
            <FileText className="mx-auto h-10 w-10 text-slate-300" />
            <p className="mt-4 text-sm font-medium text-slate-700">还没有保存的方案</p>
            <p className="mt-2 text-sm text-slate-500">
              前往工作台开始澄清对话或生成文档后，方案会自动保存到这里。
            </p>
            <button
              type="button"
              onClick={() => navigate('/v2')}
              className="mt-6 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              去新建方案
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-base font-semibold text-slate-900">{item.title}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>
                      入口：{ENTRY_MODE_LABELS[item.entry_mode || ''] || item.entry_mode || '未知'}
                    </span>
                    <span>阶段：{item.current_stage || '未知'}</span>
                    {item.status && <span>状态：{item.status}</span>}
                    <span>更新于 {formatDateTime(item.updated_at)}</span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/v2/${item.id}`)}
                    className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    继续编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(item.id, item.title)}
                    disabled={deletingId === item.id}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
