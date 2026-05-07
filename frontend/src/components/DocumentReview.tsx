import { useState, useRef, useEffect } from 'react';
import { Sparkles, X, Loader2, FileText, Copy, Check as CheckIcon } from 'lucide-react';
import type { DocAction, PrdReviewResult } from '../types';

interface DocumentReviewProps {
  title: string;
  content: string;
  streamingContent?: string;
  isGenerating?: boolean;
  isGeneratingPhase?: boolean;
  generationStatusText?: string;
  reviewResult?: PrdReviewResult | null;
  actions: DocAction[];
  onSaveEdit: (content: string) => void;
  onOptimize: (instruction: string) => void;
}

export default function DocumentReview({
  title,
  content,
  streamingContent,
  isGenerating,
  isGeneratingPhase,
  generationStatusText,
  reviewResult,
  actions,
  onSaveEdit,
  onOptimize,
}: DocumentReviewProps) {
  const [editContent, setEditContent] = useState(content);
  const [optimizeInstruction, setOptimizeInstruction] = useState('');
  const [showOptimizeInput, setShowOptimizeInput] = useState(false);
  const [copied, setCopied] = useState(false);
  const optimizeInputRef = useRef<HTMLTextAreaElement>(null);

  // content 变更时同步（优化/外部更新后）
  useEffect(() => {
    setEditContent(content);
  }, [content]);

  useEffect(() => {
    if (showOptimizeInput) optimizeInputRef.current?.focus();
  }, [showOptimizeInput]);

  // 生成/优化阶段显示流式内容（只读），稳定后显示可编辑内容
  const displayContent = (isGenerating || isGeneratingPhase) && streamingContent
    ? streamingContent
    : editContent;

  const isReadOnly = !!(isGenerating || isGeneratingPhase);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const handleTextChange = (value: string) => {
    setEditContent(value);
    onSaveEdit(value);
  };

  const handleOptimizeSubmit = () => {
    if (!optimizeInstruction.trim()) return;
    onOptimize(optimizeInstruction.trim());
    setOptimizeInstruction('');
    setShowOptimizeInput(false);
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 顶部栏 */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary-500" />
          <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
          {(isGenerating || isGeneratingPhase) && (
            <span className="flex items-center gap-1 text-sm text-primary-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {isGeneratingPhase ? (generationStatusText || '生成中...') : '优化中...'}
            </span>
          )}
        </div>
        <button
          onClick={handleCopy}
          disabled={!displayContent}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-30"
        >
          {copied ? <CheckIcon className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>

      {/* 主体：始终为可编辑 textarea */}
      <div className="flex-1 flex flex-col min-h-0 p-4">
        <textarea
          className="flex-1 w-full p-4 font-mono text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-300 disabled:bg-gray-50 disabled:text-gray-600"
          value={displayContent}
          onChange={(e) => !isReadOnly && handleTextChange(e.target.value)}
          readOnly={isReadOnly}
          spellCheck={false}
          placeholder={isGeneratingPhase ? '' : '内容将在此显示，可直接编辑...'}
        />

        {reviewResult && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">Review Agent 审查结果</h3>
                <p className="mt-1 text-sm text-gray-600">{reviewResult.summary || '已完成审查。'}</p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                reviewResult.passed
                  ? 'bg-green-100 text-green-700'
                  : 'bg-amber-100 text-amber-700'
              }`}>
                {reviewResult.passed ? '已通过' : '已提出修改'}
              </span>
            </div>

            {reviewResult.issues.length > 0 && (
              <div className="mt-3 space-y-2">
                {reviewResult.issues.map((issue, index) => (
                  <div key={`${issue.section}-${index}`} className="rounded-md bg-gray-50 p-3">
                    <div className="flex items-center gap-2 text-xs font-medium">
                      <span className={`rounded px-2 py-0.5 ${
                        issue.severity === 'high'
                          ? 'bg-red-100 text-red-700'
                          : issue.severity === 'medium'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-slate-100 text-slate-700'
                      }`}>
                        {issue.severity.toUpperCase()}
                      </span>
                      <span className="text-gray-500">{issue.section}</span>
                    </div>
                    <p className="mt-2 text-sm text-gray-800">{issue.problem}</p>
                    <p className="mt-1 text-sm text-gray-600">建议：{issue.suggestion}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 底部操作区 */}
      <div className="flex-shrink-0 border-t border-gray-100 bg-white px-6 py-4">
        {/* 优化输入框 */}
        {showOptimizeInput && !isReadOnly && (
          <div className="mb-3 flex gap-2">
            <textarea
              ref={optimizeInputRef}
              rows={2}
              placeholder="描述你想如何优化这份文档，例如：让技术规格更详细..."
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-300"
              value={optimizeInstruction}
              onChange={(e) => setOptimizeInstruction(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleOptimizeSubmit();
                }
              }}
            />
            <div className="flex flex-col gap-1">
              <button
                onClick={handleOptimizeSubmit}
                disabled={!optimizeInstruction.trim()}
                className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                确认
              </button>
              <button
                onClick={() => { setShowOptimizeInput(false); setOptimizeInstruction(''); }}
                className="px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-4 h-4 mx-auto" />
              </button>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={() => setShowOptimizeInput(!showOptimizeInput)}
            disabled={isReadOnly}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Sparkles className="w-4 h-4" />
            优化文档
          </button>

          <div className="flex items-center gap-2">
            {actions.map((action, i) => (
              <button
                key={i}
                onClick={action.onClick}
                disabled={action.disabled || isReadOnly}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  action.variant === 'primary'
                    ? 'bg-primary-600 text-white hover:bg-primary-700'
                    : action.variant === 'secondary'
                    ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    : 'text-gray-500 hover:bg-gray-50 border border-gray-200'
                }`}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
