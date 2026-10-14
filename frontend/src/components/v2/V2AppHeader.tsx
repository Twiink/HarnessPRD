import { Sparkles } from 'lucide-react';
import ArtifactProgressBar from '../ArtifactProgressBar';
import { V2_PAGE_CLASS } from '../../constants/v2Layout';
import type { ArtifactNode } from '../../utils/artifactProgress';

type V2AppHeaderProps = {
  artifactNodes: ArtifactNode[];
  onGoSessionList: () => void;
  onResetPage: () => void;
};

export default function V2AppHeader({
  artifactNodes,
  onGoSessionList,
  onResetPage,
}: V2AppHeaderProps) {
  return (
    <header className="z-20 flex-shrink-0 border-b border-slate-200 bg-white shadow-sm">
      <div className={`${V2_PAGE_CLASS} flex items-center justify-between gap-4 py-3`}>
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Vibe Coding v2</div>
            <div className="text-xs text-slate-500">结构化需求工作台</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onGoSessionList}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            我的方案
          </button>
          <button
            type="button"
            onClick={onResetPage}
            title="清空本次任务的全部进度与内容"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:border-red-300 hover:bg-red-100"
          >
            结束当前任务
          </button>
          <a href="/" className="text-sm text-slate-500 hover:text-slate-800">
            返回旧版
          </a>
        </div>
      </div>

      <div className="border-t border-slate-200/80 bg-white">
        <div className={`${V2_PAGE_CLASS} py-2`}>
          <ArtifactProgressBar nodes={artifactNodes} />
        </div>
      </div>
    </header>
  );
}
