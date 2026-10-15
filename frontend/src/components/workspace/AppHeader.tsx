import ArtifactProgressBar from '../ArtifactProgressBar';
import BrandMark from '../BrandMark';
import type { ArtifactNode } from '../../utils/artifactProgress';

type AppHeaderProps = {
  artifactNodes: ArtifactNode[];
  projectName?: string;
  onGoSessionList: () => void;
  onResetPage: () => void;
};

export default function AppHeader({
  artifactNodes,
  projectName,
  onGoSessionList,
  onResetPage,
}: AppHeaderProps) {
  return (
    <header className="z-20 flex flex-shrink-0 flex-wrap items-stretch border-b-[1.5px] border-ink bg-sheet lg:h-[52px] lg:flex-nowrap">
      <div className="flex h-[52px] shrink-0 items-center gap-4 px-5 text-ink lg:px-7">
        <BrandMark />
        {projectName && (
          <span className="hidden max-w-[16rem] truncate border-l border-hair pl-4 text-[13px] text-slate-500 xl:block">
            {projectName}
          </span>
        )}
      </div>

      <div className="order-last flex h-11 w-full min-w-0 items-stretch border-t border-hair lg:order-none lg:h-auto lg:w-auto lg:flex-1 lg:border-t-0">
        <ArtifactProgressBar nodes={artifactNodes} />
      </div>

      <div className="ml-auto flex h-[52px] shrink-0 items-center gap-1 px-3 lg:px-5">
        <button type="button" onClick={onGoSessionList} className="btn-quiet">
          我的方案
        </button>
        <button
          type="button"
          onClick={onResetPage}
          title="清空本次任务的全部进度与内容"
          className="btn-quiet hover:text-mark"
        >
          结束任务
        </button>
      </div>
    </header>
  );
}
