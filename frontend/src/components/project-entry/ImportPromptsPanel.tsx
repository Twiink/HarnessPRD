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
        <h1 className="text-2xl font-semibold text-slate-900">导入 PRD 与接口文档</h1>
        <p className="mt-2 text-sm text-slate-500">
          粘贴 PRD（必填）与接口文档（可选），直接生成提示词套件。
        </p>
      </div>

      <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <FieldLabel title="PRD 内容" hint="生成提示词时，PRD 为必填" />
          <TextArea
            rows={14}
            value={manualPrdInput}
            onChange={(e) => onManualPrdInputChange(e.target.value)}
            placeholder="在这里粘贴完整 PRD..."
          />
        </div>
        <div>
          <FieldLabel title="接口文档内容（可选）" hint="如果已有接口文档，提示词会更完整" />
          <TextArea
            rows={14}
            value={manualApiDocsInput}
            onChange={(e) => onManualApiDocsInputChange(e.target.value)}
            placeholder="可选：粘贴接口文档..."
          />
        </div>
        <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
          <button
            type="button"
            onClick={onEnterStage}
            disabled={actionLocked}
            className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            进入当前环节
          </button>
          <button
            type="button"
            onClick={onStartPrompts}
            disabled={actionLocked}
            className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            直接生成提示词
          </button>
        </div>
      </div>
    </div>
  );
}
