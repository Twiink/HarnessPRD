import { Loader2 } from 'lucide-react';
import BrandMark from '../BrandMark';

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
    <div className="flex h-screen flex-col bg-ground p-4 lg:p-5">
      <div className="sheet flex flex-1 flex-col">
        <div className="flex h-[52px] items-center border-b-[1.5px] border-ink px-6 text-ink">
          <BrandMark />
        </div>
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md">
            <h1 className="text-2xl font-semibold tracking-[-0.01em] text-ink">{title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button type="button" onClick={onGoList} className="btn-outline">
                查看我的方案
              </button>
              <button type="button" onClick={onGoNew} className="btn-primary">
                新建方案
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SessionLoadingPage() {
  return (
    <div className="flex h-screen items-center justify-center gap-2 bg-ground text-sm text-slate-600">
      <Loader2 className="h-4 w-4 animate-spin text-primary-600" aria-hidden />
      正在加载方案
    </div>
  );
}
