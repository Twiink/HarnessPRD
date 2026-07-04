import { Sparkles } from 'lucide-react';

type SessionLoadErrorPageProps = {
  title: string;
  description: string;
  onGoList: () => void;
  onGoNew: () => void;
};

export default function SessionLoadErrorPage({
  title,
  description,
  onGoList,
  onGoNew,
}: SessionLoadErrorPageProps) {
  return (
    <div className="flex h-screen flex-col items-center justify-center bg-slate-50 px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white">
          <Sparkles className="h-5 w-5" />
        </div>
        <h1 className="mt-6 text-lg font-semibold text-slate-900">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={onGoList}
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            查看我的方案
          </button>
          <button
            type="button"
            onClick={onGoNew}
            className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          >
            新建方案
          </button>
        </div>
      </div>
    </div>
  );
}

export function SessionLoadingPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
      加载方案中…
    </div>
  );
}
