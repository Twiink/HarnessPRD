import { useState, useRef, useEffect } from 'react';
import { Sparkles, X, Loader2, FileText, Copy, Download, Check as CheckIcon } from 'lucide-react';
import type { DocAction, PrdReviewResult, RunSummary } from '../types';
import type { QualityGateResult } from '../types/qualityGate';
import GenerationStepper, { type StepItem } from './GenerationStepper';
import RunSummaryPanel from './RunSummaryPanel';
import ReviewResultPanel from './ReviewResultPanel';
import QualityReportPanel from './QualityReportPanel';
import { shouldShowReviewPanel } from '../utils/prdReviewDisplay';

interface DocumentReviewProps {
  title: string;
  content: string;
  streamingContent?: string;
  isGenerating?: boolean;
  isGeneratingPhase?: boolean;
  generationStatusText?: string;
  generationSteps?: StepItem[];
  generationElapsed?: number;
  generationHint?: string;
  runSummary?: RunSummary | null;
  reviewResult?: PrdReviewResult | null;
  /** 是否已按审查意见自动修订；优先于 runSummary.revision_applied */
  revisionApplied?: boolean;
  qualityGate?: QualityGateResult | null;
  /** 下载文件名，如 `朋友圈文案助手-PRD.md`；不传则根据标题自动推断 */
  downloadFilename?: string;
  actions: DocAction[];
  onSaveEdit: (content: string) => void;
  onOptimize: (instruction: string) => void;
  versionPanel?: React.ReactNode;
  isPreviewMode?: boolean;
  previewLabel?: string;
  onRestorePreview?: () => void;
  isRestoring?: boolean;
}

export type { DocumentReviewProps };

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.md') ? filename : `${filename}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

function resolveDownloadFilename(title: string, custom?: string): string {
  if (custom?.trim()) {
    const name = custom.trim();
    return name.endsWith('.md') ? name : `${name}.md`;
  }
  if (title.includes('PRD')) return 'PRD.md';
  if (title.includes('接口')) return 'API-Docs.md';
  if (title.includes('提示词')) return 'Prompts.md';
  return 'document.md';
}

export default function DocumentReview({
  title,
  content,
  streamingContent,
  isGenerating,
  isGeneratingPhase,
  generationStatusText,
  generationSteps,
  generationElapsed,
  generationHint,
  runSummary,
  reviewResult,
  revisionApplied,
  qualityGate,
  downloadFilename,
  actions,
  onSaveEdit,
  onOptimize,
  versionPanel,
  isPreviewMode,
  previewLabel,
  onRestorePreview,
  isRestoring,
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

  const isReadOnly = !!(isGenerating || isGeneratingPhase || isPreviewMode);
  const showRevisionApplied = revisionApplied ?? runSummary?.revision_applied ?? false;
  const showStepper = !!(generationSteps && generationSteps.length > 0);
  const showHeaderLoader = (isGenerating || isGeneratingPhase) && !showStepper;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const handleDownload = () => {
    if (!displayContent.trim()) return;
    downloadMarkdown(resolveDownloadFilename(title, downloadFilename), displayContent);
  };

  const handleTextChange = (value: string) => {
    if (isPreviewMode) return;
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
    <div className="flex h-full min-h-0 flex-col bg-white">
      {/* 顶部栏 */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-gray-100 px-6 py-3">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary-500" />
          <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
          {showHeaderLoader && (
            <span className="flex items-center gap-1 text-sm text-primary-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {isGeneratingPhase ? (generationStatusText || '生成中...') : '优化中...'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleCopy}
            disabled={!displayContent}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-30"
          >
            {copied ? <CheckIcon className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? '已复制' : '复制'}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={!displayContent}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-30"
          >
            <Download className="h-3.5 w-3.5" />
            下载
          </button>
        </div>
      </div>

      {showStepper && (
        <GenerationStepper
          steps={generationSteps!}
          elapsedSeconds={generationElapsed ?? 0}
          hint={generationHint}
        />
      )}

      {/* 主体：文档撑满，Review 结果在下方滚动 */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {isPreviewMode && previewLabel && onRestorePreview && (
            <div className="flex flex-shrink-0 items-center justify-between gap-3 border-b border-amber-100 bg-amber-50 px-4 py-2">
              <p className="text-sm text-amber-800">
                正在预览 {previewLabel}，恢复后将基于该版本创建新版本
              </p>
              <button
                type="button"
                onClick={onRestorePreview}
                disabled={isRestoring}
                className="flex flex-shrink-0 items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRestoring ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                恢复此版本
              </button>
            </div>
          )}

          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
          <textarea
            className="min-h-[12rem] w-full flex-1 resize-none rounded-lg border border-gray-200 bg-gray-50 p-4 font-mono text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-primary-300 disabled:bg-gray-50 disabled:text-gray-600"
            value={displayContent}
            onChange={(e) => !isReadOnly && handleTextChange(e.target.value)}
            readOnly={isReadOnly}
            spellCheck={false}
            placeholder={isGeneratingPhase ? '' : '内容将在此显示，可直接编辑...'}
          />
          </div>

          {!versionPanel && shouldShowReviewPanel(reviewResult) && (
            <ReviewResultPanel
              review={reviewResult!}
              revisionApplied={showRevisionApplied}
              className="flex-shrink-0"
            />
          )}

          {qualityGate && (
            <QualityReportPanel qualityGate={qualityGate} className="flex-shrink-0" />
          )}

          <RunSummaryPanel summary={runSummary ?? null} />
        </div>

        {versionPanel}
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
                    : action.variant === 'link'
                    ? 'px-2 text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline'
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
