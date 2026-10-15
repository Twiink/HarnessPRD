import { useState, useRef, useEffect } from 'react';
import { Wand2, X, Loader2, Copy, Download, Check as CheckIcon } from 'lucide-react';
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
    <div className="flex h-full min-h-0 flex-col bg-sheet">
      {/* 顶部栏 */}
      <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-hair px-6 py-3.5 lg:px-8">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[22px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
          {showHeaderLoader && (
            <span className="flex items-center gap-1.5 text-sm text-primary-600">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              {isGeneratingPhase ? (generationStatusText || '正在生成') : '正在优化'}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1 whitespace-nowrap">
          <button
            type="button"
            onClick={handleCopy}
            disabled={!displayContent}
            className="btn-quiet py-1.5"
          >
            {copied ? <CheckIcon className="h-3.5 w-3.5 text-primary-600" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
            {copied ? '已复制' : '复制'}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={!displayContent}
            className="btn-quiet py-1.5"
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
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {isPreviewMode && previewLabel && onRestorePreview && (
            <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-3 border-b border-stamp/30 bg-amber-50 px-6 py-2 lg:px-8">
              <p className="text-sm text-amber-900">
                正在查看 {previewLabel} 的版本。恢复后它会成为当前工作稿，原记录保留。
              </p>
              <button
                type="button"
                onClick={onRestorePreview}
                disabled={isRestoring}
                className="btn-primary py-1 text-xs"
              >
                {isRestoring ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : null}
                恢复此版本
              </button>
            </div>
          )}

          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-5 lg:px-8">
          <textarea
            aria-label={`${title}正文`}
            className="min-h-[12rem] w-full flex-1 resize-none rounded border border-hair bg-white px-6 py-5 font-sans text-[14px] leading-[1.8] text-ink focus:border-primary-600 focus:outline-none focus:ring-1 focus:ring-primary-600 read-only:bg-slate-50 read-only:text-slate-700"
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
      <div className="flex-shrink-0 border-t-[1.5px] border-ink bg-sheet px-6 py-3.5 lg:px-8">
        {/* 优化输入框 */}
        {showOptimizeInput && !isReadOnly && (
          <div className="mb-3 flex gap-2">
            <textarea
              ref={optimizeInputRef}
              rows={2}
              aria-label="优化要求"
              placeholder="写下要怎么改，例如：补充交易纠纷的处理流程"
              className="flex-1 resize-none rounded border border-slate-300 bg-white px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:border-primary-600 focus:outline-none focus:ring-1 focus:ring-primary-600"
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
                className="btn-primary py-1.5"
              >
                开始优化
              </button>
              <button
                onClick={() => { setShowOptimizeInput(false); setOptimizeInstruction(''); }}
                className="btn-quiet py-1.5"
                aria-label="取消优化"
              >
                <X className="mx-auto h-4 w-4" aria-hidden />
              </button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            onClick={() => setShowOptimizeInput(!showOptimizeInput)}
            disabled={isReadOnly}
            aria-expanded={showOptimizeInput}
            className="btn-quiet -ml-3"
          >
            <Wand2 className="h-4 w-4" aria-hidden />
            按意见优化
          </button>

          <div className="flex flex-wrap items-center gap-2">
            {actions.map((action, i) => (
              <button
                key={i}
                onClick={action.onClick}
                disabled={action.disabled || isReadOnly}
                className={`max-w-full ${
                  action.variant === 'primary'
                    ? 'btn-primary'
                    : action.variant === 'secondary'
                    ? 'btn-outline'
                    : action.variant === 'link'
                    ? 'btn border-transparent px-2 text-slate-600 underline-offset-2 hover:text-ink hover:underline'
                    : 'btn-quiet'
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
