import { ArrowLeft } from 'lucide-react';
import { FieldLabel, TextArea } from './formPrimitives';

type ImportPromptsPanelProps = {
  manualPrdInput: string;
  manualApiDocsInput: string;
  onManualPrdInputChange: (value: string) => void;
  onManualApiDocsInputChange: (value: string) => void;
  onEnterStage: () => void;
  onStartPrompts: () => void;
  onBack: () => void;
  actionLocked: boolean;
};

export default function ImportPromptsPanel({
  manualPrdInput,
  manualApiDocsInput,
  onManualPrdInputChange,
  onManualApiDocsInputChange,
  onEnterStage,
  onStartPrompts,
  onBack,
  actionLocked,
}: ImportPromptsPanelProps) {
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
        <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-ink">导入 PRD 和接口文档</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">PRD 必填，接口文档可选。填好后直接生成开发提示词。</p>
      </div>

      <div className="sheet space-y-6 p-6 lg:p-8">
        <div>
          <FieldLabel title="PRD 内容" hint="生成提示词时，PRD 为必填" />
          <TextArea
            rows={14}
            value={manualPrdInput}
            onChange={(e) => onManualPrdInputChange(e.target.value)}
            placeholder="粘贴 PRD 的 Markdown 正文"
          />
        </div>
        <div>
          <FieldLabel title="接口文档内容（可选）" hint="如果已有接口文档，提示词会更完整" />
          <TextArea
            rows={14}
            value={manualApiDocsInput}
            onChange={(e) => onManualApiDocsInputChange(e.target.value)}
            placeholder="粘贴接口文档的 Markdown 正文"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-3 border-t border-hair pt-5">
          <button
            type="button"
            onClick={onEnterStage}
            disabled={actionLocked}
            className="btn-outline px-5 py-2.5"
          >
            进入当前环节
          </button>
          <button
            type="button"
            onClick={onStartPrompts}
            disabled={actionLocked}
            className="btn-primary px-5 py-2.5"
          >
            直接生成提示词
          </button>
        </div>
      </div>
    </div>
  );
}
