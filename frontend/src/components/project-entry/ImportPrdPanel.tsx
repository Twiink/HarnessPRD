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
    <div className="mx-auto max-w-5xl">
      <button
        type="button"
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        返回起点选择
      </button>

      <div className="mb-6">
        <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-ink">导入 PRD</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">粘贴现成的 PRD。可以先进入审阅，也可以直接生成接口文档。</p>
      </div>

      <div className="sheet space-y-6 p-6 lg:p-8">
        <div>
          <FieldLabel title="PRD 内容" hint="粘贴完整 PRD 正文" />
          <TextArea
            rows={20}
            value={manualPrdInput}
            onChange={(e) => onManualPrdInputChange(e.target.value)}
            placeholder="粘贴 PRD 的 Markdown 正文"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-3 border-t border-hair pt-5">
          <button
            type="button"
            onClick={onEnterPrdReview}
            disabled={actionLocked}
            className="btn-outline px-5 py-2.5"
          >
            进入 PRD 环节
          </button>
          <button
            type="button"
            onClick={onStartApiDocs}
            disabled={actionLocked}
            className="btn-primary px-5 py-2.5"
          >
            直接生成接口文档
          </button>
        </div>
      </div>
    </div>
  );
}
