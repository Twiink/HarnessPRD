import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ClarificationGenerateConfirmModal from './ClarificationGenerateConfirmModal';
import { PAGE_CLASS } from '../../constants/layout';
import MessageList from '../MessageList';
import ChatInput from '../ChatInput';
import ClarificationWarnBanner from '../ClarificationWarnBanner';
import ClarificationContextPanel from '../ClarificationContextPanel';
import { getVisibleClarificationMessages } from '../../utils/viewState';
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
      <div className="flex-shrink-0 border-b border-hair bg-sheet py-3">
        <div className={`${PAGE_CLASS} flex flex-wrap items-center justify-between gap-3`}>
          <div className="min-w-0 flex flex-wrap items-center gap-3">
            <div>
              <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-ink">澄清需求</h1>
              <div className="text-xs text-slate-500">逐个回答问题，答案会在生成 PRD 前回填到需求里</div>
            </div>
            {clarificationState.statusLabel && (
              <span
                className={`rounded-sm border px-2 text-xs font-medium leading-[22px] ${clarificationStatusClass(
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
              className="btn-quiet"
            >
              返回需求表
            </button>
            <button
              type="button"
              onClick={handleGenerateClick}
              disabled={generateDisabled}
              title={
                generateWarn ? '还有问题没回答，点击后会先让你确认' : undefined
              }
              className={generateWarn ? 'btn-outline' : 'btn-primary'}
            >
              {isSyncingSummary ? '正在整理对话' : '结束澄清，生成 PRD'}
            </button>
          </div>
        </div>
      </div>

      <div
        ref={chatScrollRef}
        onScroll={handleChatScroll}
        className="min-h-0 flex-1 overflow-y-auto bg-sheet"
      >
        <div className={PAGE_CLASS}>
          <MessageList messages={displayMessages} loading={isStreaming && streamingContent === ''} />
          <div ref={messagesEndRef} className="h-px shrink-0" aria-hidden />
        </div>
      </div>

      <div className="flex-shrink-0 border-t-[1.5px] border-ink bg-sheet pb-4 pt-3">
        <div className={PAGE_CLASS}>
          <div className="mx-auto max-w-3xl">
            <ClarificationContextPanel rounds={obs.clarificationRounds} />
          </div>
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
