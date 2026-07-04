import { Check } from 'lucide-react';
import type { ArtifactNode } from '../utils/artifactProgress';

type ArtifactProgressBarProps = {
  nodes: ArtifactNode[];
};

export default function ArtifactProgressBar({ nodes }: ArtifactProgressBarProps) {
  return (
    <nav className="flex min-w-0 flex-1 items-center gap-3" aria-label="产出物进度">
      <span className="shrink-0 text-xs font-medium text-slate-500">产出物</span>
      <ol className="flex min-w-0 flex-1 flex-wrap items-center gap-y-1">
        {nodes.map((node, index) => {
          const isLast = index === nodes.length - 1;
          const isActive = node.status === 'active';
          const isDone = node.status === 'done';
          const showCheck = node.completed;
          const canClick = node.clickable;

          let buttonClass =
            'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ';
          if (isActive) {
            buttonClass +=
              'bg-primary-50 text-primary-800 font-semibold cursor-default';
          } else if (isDone) {
            buttonClass += canClick
              ? 'text-slate-600 hover:bg-slate-50 cursor-pointer'
              : 'text-slate-600';
          } else {
            buttonClass += 'cursor-default text-slate-300';
          }

          const connectorDone = showCheck || isActive;

          return (
            <li key={node.id} className="flex items-center">
              <button
                type="button"
                onClick={node.onClick}
                disabled={!canClick && !isActive}
                title={node.title}
                aria-current={isActive ? 'step' : undefined}
                className={buttonClass}
              >
                <span>{node.label}</span>
                {showCheck && (
                  <Check className="h-3 w-3 shrink-0 stroke-[2.5] text-primary-500" aria-hidden />
                )}
              </button>
              {!isLast && (
                <span
                  className={`mx-1.5 hidden h-px w-5 sm:block ${
                    connectorDone ? 'bg-primary-200' : 'bg-slate-200'
                  }`}
                  aria-hidden
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
