import { Check } from 'lucide-react';
import type { ArtifactNode } from '../utils/artifactProgress';

type ArtifactProgressBarProps = {
  nodes: ArtifactNode[];
};

/** 图纸分册编号：A 需求、B 澄清… 与流程顺序对应 */
const SHEET_CODES = ['A', 'B', 'C', 'D', 'E'];

export default function ArtifactProgressBar({ nodes }: ArtifactProgressBarProps) {
  return (
    <nav className="flex h-full min-w-0 items-stretch" aria-label="产出物进度">
      <ol className="flex h-full min-w-0 items-stretch overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {nodes.map((node, index) => {
          const isActive = node.status === 'active';
          const isDone = node.completed;
          const canClick = node.clickable;

          let cls =
            'group flex h-full items-center gap-2 border-l border-hair px-4 text-[13px] transition-colors first:border-l-0 lg:first:border-l ';
          if (isActive) {
            cls += 'cursor-default bg-ink text-white';
          } else if (canClick) {
            cls += 'cursor-pointer text-ink hover:bg-slate-100';
          } else if (isDone) {
            cls += 'cursor-default text-ink';
          } else {
            cls += 'cursor-default text-slate-400';
          }

          return (
            <li key={node.id} className="flex items-stretch last:border-r last:border-hair">
              <button
                type="button"
                onClick={node.onClick}
                disabled={!canClick && !isActive}
                title={node.title}
                aria-current={isActive ? 'step' : undefined}
                className={cls}
              >
                <span
                  className={`font-cond text-xs font-semibold ${
                    isActive ? 'text-primary-200' : isDone ? 'text-primary-600' : 'text-slate-400'
                  }`}
                  aria-hidden
                >
                  {SHEET_CODES[index] ?? index + 1}
                </span>
                <span className="whitespace-nowrap">{node.label}</span>
                {isDone && !isActive && (
                  <Check className="h-3.5 w-3.5 shrink-0 stroke-[2.5] text-primary-600" aria-label="已完成" />
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
