import { ArrowRight } from 'lucide-react';

type ProjectEntryChooserProps = {
  onSelectStructured: () => void;
  onSelectImportPrd: () => void;
  onSelectImportPrompts: () => void;
};

const STAGES = ['需求', '澄清', 'PRD', '接口文档', '提示词'];

type Route = {
  key: string;
  title: string;
  description: string;
  /** 该起点覆盖的流程阶段下标 */
  from: number;
  onClick: () => void;
  primary?: boolean;
};

export default function ProjectEntryChooser({
  onSelectStructured,
  onSelectImportPrd,
  onSelectImportPrompts,
}: ProjectEntryChooserProps) {
  const routes: Route[] = [
    {
      key: 'structured',
      title: '从零整理需求',
      description: '填写结构化需求表，和 AI 澄清不清楚的地方，再依次生成 PRD、接口文档和提示词。',
      from: 0,
      onClick: onSelectStructured,
      primary: true,
    },
    {
      key: 'prd',
      title: '已有 PRD',
      description: '粘贴现成的 PRD，审阅后继续生成接口文档。',
      from: 2,
      onClick: onSelectImportPrd,
    },
    {
      key: 'prompts',
      title: '已有 PRD 和接口文档',
      description: '直接生成开发提示词，并导出交付包。',
      from: 3,
      onClick: onSelectImportPrompts,
    },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-10 max-w-2xl">
        <h1 className="text-[34px] font-semibold leading-tight tracking-[-0.02em] text-ink">
          新建方案
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-slate-600">
          ReqFlow 把一个软件想法整理成可交付开发的文档。选择你手上已有的材料，从对应的环节开始。
        </p>
      </div>

      <div className="sheet">
        {/* 流程总图：列对应五个阶段 */}
        <div className="grid grid-cols-[minmax(0,1fr)] md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="hidden border-b border-hair px-6 py-3 text-xs text-slate-500 md:block">起点</div>
          <div className="hidden grid-cols-5 border-b border-l border-hair md:grid">
            {STAGES.map((stage, i) => (
              <div key={stage} className="flex items-center gap-1.5 border-l border-hair px-3 py-3 text-xs text-slate-500 first:border-l-0">
                <span className="font-cond font-semibold text-primary-600">{'ABCDE'[i]}</span>
                {stage}
              </div>
            ))}
          </div>

          {routes.map((route, ri) => (
            <button
              key={route.key}
              type="button"
              onClick={route.onClick}
              className={`group col-span-full grid grid-cols-subgrid text-left transition-colors hover:bg-primary-50/60 ${
                ri < routes.length - 1 ? 'border-b border-hair' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-4 px-6 py-6">
                <div>
                  <div className="flex items-center gap-2 text-[17px] font-semibold text-ink">
                    {route.title}
                    {route.primary && (
                      <span className="rounded-sm border border-primary-600 px-1.5 text-[11px] font-medium leading-[18px] text-primary-600">
                        完整流程
                      </span>
                    )}
                  </div>
                  <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-600">{route.description}</p>
                </div>
                <ArrowRight
                  className="mt-1 h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-primary-600 md:hidden"
                  aria-hidden
                />
              </div>

              {/* 覆盖范围：一条从起点画到终点的标注线 */}
              <div className="relative hidden grid-cols-5 border-l border-hair md:grid" aria-hidden>
                {STAGES.map((stage) => (
                  <div key={stage} className="border-l border-hair first:border-l-0" />
                ))}
                <div
                  className="absolute top-1/2 h-px -translate-y-1/2 bg-ink transition-colors group-hover:bg-primary-600"
                  style={{ left: `calc(${(route.from / STAGES.length) * 100}% + 10%)`, right: '10%' }}
                />
                <span
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-ink bg-sheet transition-colors group-hover:border-primary-600 group-hover:bg-primary-600"
                  style={{ left: `calc(${(route.from / STAGES.length) * 100}% + 10%)` }}
                />
                <span
                  className="absolute right-[10%] top-1/2 h-0 w-0 -translate-y-1/2 translate-x-full border-y-[4px] border-l-[7px] border-y-transparent border-l-ink transition-colors group-hover:border-l-primary-600"
                />
              </div>
            </button>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        方案会自动保存，可以随时在「我的方案」中继续。
      </p>
    </div>
  );
}
