import { ChevronDown, ChevronUp, Code2 } from 'lucide-react';
import type { QuestionConfig, QuestionsConfig } from '../types';

interface FormStepProps {
  questions: QuestionsConfig;
  formData: Record<string, string>;
  onChange: (id: string, value: string) => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
  onSubmit: () => void;
  loading: boolean;
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: string;
  onChange: (val: string) => void;
}) {
  const baseInputClass =
    'w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <label className="text-sm font-medium text-gray-800">
          {question.label}
          {question.required && <span className="ml-1 text-red-400">*</span>}
        </label>
      </div>
      {question.description && (
        <p className="text-xs text-gray-500">{question.description}</p>
      )}

      {question.type === 'text' && (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={question.placeholder}
          className={baseInputClass}
        />
      )}

      {question.type === 'textarea' && (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={question.placeholder}
          rows={3}
          className={`${baseInputClass} resize-none`}
        />
      )}

      {question.type === 'select' && (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`${baseInputClass} bg-white`}
        >
          <option value="">请选择...</option>
          {question.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      )}

      {question.type === 'radio' && (
        <div className="flex flex-wrap gap-2">
          {question.options?.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${
                value === opt
                  ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function FormStep({
  questions,
  formData,
  onChange,
  showAdvanced,
  onToggleAdvanced,
  onSubmit,
  loading,
}: FormStepProps) {
  const allQuestions = showAdvanced
    ? [...questions.base_questions, ...questions.advanced_questions]
    : questions.base_questions;

  const requiredFilled = questions.base_questions
    .filter((q) => q.required)
    .every((q) => formData[q.id]?.trim());

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">描述你的产品想法</h2>
          <p className="text-sm text-gray-500">
            填写你已知的信息，不确定的可以留空——AI 会帮你一起想清楚
          </p>
        </div>

        <div className="space-y-5">
          {allQuestions.map((q) => (
            <QuestionField
              key={q.id}
              question={q}
              value={formData[q.id] || ''}
              onChange={(val) => onChange(q.id, val)}
            />
          ))}
        </div>

        {/* 高级选项切换 */}
        <button
          type="button"
          onClick={onToggleAdvanced}
          className="mt-6 flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <Code2 className="w-4 h-4" />
          {showAdvanced ? '隐藏开发者选项' : '显示开发者高级选项'}
          {showAdvanced ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>

        <button
          onClick={onSubmit}
          disabled={loading || !requiredFilled}
          className="mt-6 w-full py-3 px-6 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {loading ? '正在连接 AI...' : '开始 AI 对话'}
        </button>

        {!requiredFilled && (
          <p className="mt-2 text-xs text-center text-gray-400">
            请填写带 <span className="text-red-400">*</span> 的必填项
          </p>
        )}
      </div>
    </div>
  );
}
