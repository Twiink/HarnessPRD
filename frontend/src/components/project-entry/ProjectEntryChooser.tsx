import { FileInput, PenLine, Upload } from 'lucide-react';

type ProjectEntryChooserProps = {
  onSelectStructured: () => void;
  onSelectImportPrd: () => void;
  onSelectImportPrompts: () => void;
};

export default function ProjectEntryChooser({
  onSelectStructured,
  onSelectImportPrd,
  onSelectImportPrompts,
}: ProjectEntryChooserProps) {
  return (
    <div className="mx-auto max-w-3xl py-4">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">新建 PRD 方案</h1>
        <p className="mt-2 text-sm text-slate-500">选择本次工作的起点</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <button
          type="button"
          onClick={onSelectStructured}
          className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition-all hover:border-slate-300 hover:shadow-md"
        >
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white">
            <PenLine className="h-5 w-5" />
          </div>
          <div className="text-base font-semibold text-slate-900">从零创建 PRD</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">
            填写结构化需求，经澄清对话后生成 PRD、接口文档与提示词。
          </p>
          <span className="mt-4 text-sm font-medium text-slate-900 group-hover:underline">
            开始填写 →
          </span>
        </button>

        <div className="flex flex-col rounded-2xl border border-slate-200 bg-slate-50/80 p-6 shadow-sm">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700">
            <Upload className="h-5 w-5" />
          </div>
          <div className="text-base font-semibold text-slate-900">导入已有素材</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">
            已有 PRD 或接口文档，从中间环节继续生成。
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <button
              type="button"
              onClick={onSelectImportPrd}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <FileInput className="h-4 w-4" />
              我有 PRD
            </button>
            <button
              type="button"
              onClick={onSelectImportPrompts}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <FileInput className="h-4 w-4" />
              我有 PRD + 接口文档
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
