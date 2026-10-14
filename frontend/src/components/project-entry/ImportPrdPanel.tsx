import { ArrowLeft } from 'lucide-react';
import { FieldLabel, TextArea } from './formPrimitives';

type ImportPrdPanelProps = {
  manualPrdInput: string;
  onManualPrdInputChange: (value: string) => void;
  onEnterPrdReview: () => void;
  onStartApiDocs: () => void;
  onBack: () => void;
  actionLocked: boolean;
};

export default function ImportPrdPanel({
  manualPrdInput,
  onManualPrdInputChange,
  onEnterPrdReview,
  onStartApiDocs,
  onBack,
  actionLocked,
}: ImportPrdPanelProps) {
  return (
    <div className="mx-auto max-w-4xl">
      <button
        type="button"
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" />
        返回路径选择
      </button>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">导入 PRD</h1>
        <p className="mt-2 text-sm text-slate-500">
          粘贴现成 PRD 后，可进入审阅或继续生成接口文档。
        </p>
      </div>

      <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <FieldLabel title="PRD 内容" hint="粘贴完整 PRD 正文" />
          <TextArea
            rows={20}
            value={manualPrdInput}
            onChange={(e) => onManualPrdInputChange(e.target.value)}
            placeholder="在这里粘贴完整 PRD..."
          />
        </div>
        <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
          <button
            type="button"
            onClick={onEnterPrdReview}
            disabled={actionLocked}
            className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            进入 PRD 环节
          </button>
          <button
            type="button"
            onClick={onStartApiDocs}
            disabled={actionLocked}
            className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            直接生成接口文档
          </button>
        </div>
      </div>
    </div>
  );
}
