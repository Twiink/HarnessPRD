import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ClarificationGenerateConfirmModal from './ClarificationGenerateConfirmModal';
import { V2_PAGE_CLASS } from '../../constants/v2Layout';
import MessageList from '../MessageList';
import ChatInput from '../ChatInput';
import ClarificationWarnBanner from '../ClarificationWarnBanner';
import ClarificationContextPanel from '../ClarificationContextPanel';
import { getVisibleClarificationMessages } from '../../utils/v2ViewState';
import { clarificationStatusClass } from '../../utils/clarificationState';
import type { ClarificationState } from '../../types/clarificationState';
import type { Message } from '../../types';
import type { useGenerationObservability } from '../../hooks/useGenerationObservability';

type ClarificationObservability = Pick<
  ReturnType<typeof useGenerationObservability>,
  'clarificationRounds' | 'contextUsage'
>;

export type ClarificationStageProps = {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  isSyncingSummary: boolean;
  actionLocked: boolean;
  clarificationState: ClarificationState;
  obs: ClarificationObservability;
  onBackToForm: () => void;
  onResetPage: () => void;
  onSyncSummary: () => void;
  onSendMessage: (input: string) => void;
};

export default function ClarificationStage({
  messages,
  streamingContent,
  isStreaming,
  isSyncingSummary,
  actionLocked,
  clarificationState,
  obs,
  onBackToForm,
  onResetPage,
  onSyncSummary,
  onSendMessage,
}: ClarificationStageProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const shouldStickToBottomRef = useRef(true);

  const displayMessages = useMemo(() => {
    const visible = getVisibleClarificationMessages(messages);
    if (streamingContent && isStreaming) {
      return [...visible, { role: 'ai' as const, content: streamingContent }];
    }
    return visible;
  }, [messages, streamingContent, isStreaming]);

  const scrollChatToBottom = useCallback((instant = false) => {
    const container = chatScrollRef.current;
    if (!container) return;
    if (instant) {
      container.scrollTop = container.scrollHeight;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  const handleChatScroll = useCallback(() => {
    const container = chatScrollRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    shouldStickToBottomRef.current = distanceFromBottom < 96;
  }, []);

  useEffect(() => {
    if (!shouldStickToBottomRef.current) return;
    const frame = requestAnimationFrame(() => {
      scrollChatToBottom(isStreaming);
    });
    return () => cancelAnimationFrame(frame);
  }, [displayMessages, streamingContent, isStreaming, scrollChatToBottom]);

  const handleSend = useCallback(
    (input: string) => {
      shouldStickToBottomRef.current = true;
      onSendMessage(input);
    },
    [onSendMessage],
  );

  const generateDisabled = isStreaming || isSyncingSummary || actionLocked;
  const generateWarn = clarificationState.needsConfirmBeforeGenerate;
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleGenerateClick = useCallback(() => {
    if (generateDisabled) return;
    if (clarificationState.needsConfirmBeforeGenerate) {
      setConfirmOpen(true);
      return;
    }
    onSyncSummary();
  }, [generateDisabled, clarificationState.needsConfirmBeforeGenerate, onSyncSummary]);

  const handleConfirmGenerate = useCallback(() => {
    setConfirmOpen(false);
    onSyncSummary();
  }, [onSyncSummary]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-shrink-0 border-b border-slate-200 bg-white py-3">
        <div className={`${V2_PAGE_CLASS} flex flex-wrap items-center justify-between gap-3`}>
          <div className="min-w-0 flex flex-wrap items-center gap-3">
            <div>
              <div className="text-sm font-medium text-slate-900">澄清对话</div>
              <div className="text-xs text-slate-500">AI 会围绕结构化摘要补齐不清晰项</div>
            </div>
            {clarificationState.statusLabel && (
              <span
                className={`rounded-lg px-2.5 py-1 text-xs font-medium ${clarificationStatusClass(
                  clarificationState,
                )}`}
              >
                {clarificationState.statusLabel}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onBackToForm}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
            >
              返回表单
            </button>
            <button
              type="button"
              onClick={onResetPage}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
            >
              结束任务
            </button>
            <button
              type="button"
              onClick={handleGenerateClick}
              disabled={generateDisabled}
              title={
                generateWarn ? '仍有待澄清问题，点击后将提示确认' : undefined
              }
              className={`rounded-lg px-3 py-2 text-xs font-medium text-white disabled:opacity-50 ${
                generateWarn
                  ? 'border border-amber-400 bg-amber-600 hover:bg-amber-700'
                  : 'bg-slate-900 hover:bg-slate-800'
              }`}
            >
              {isSyncingSummary ? '分析对话中…' : generateWarn ? '生成 PRD ⚠' : '生成 PRD'}
            </button>
          </div>
        </div>
      </div>

      <div
        ref={chatScrollRef}
        onScroll={handleChatScroll}
        className="min-h-0 flex-1 overflow-y-auto bg-slate-50/40"
      >
        <div className={V2_PAGE_CLASS}>
          <MessageList messages={displayMessages} loading={isStreaming && streamingContent === ''} />
          <div ref={messagesEndRef} className="h-px shrink-0" aria-hidden />
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-slate-200 bg-white pb-4 pt-3">
        <div className={V2_PAGE_CLASS}>
          <ClarificationContextPanel rounds={obs.clarificationRounds} />
          <ClarificationWarnBanner
            visible={obs.contextUsage?.level === 'warn' || obs.contextUsage?.level === 'exceed'}
          />
          <ChatInput onSend={handleSend} loading={isStreaming} />
        </div>
      </div>

      <ClarificationGenerateConfirmModal
        open={confirmOpen}
        state={clarificationState}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleConfirmGenerate}
      />
    </div>
  );
}
