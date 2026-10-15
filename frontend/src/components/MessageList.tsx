import ReactMarkdown from 'react-markdown';
import type { Message } from '../types';

interface MessageListProps {
  messages: Message[];
  loading?: boolean;
}

/**
 * 澄清对话按“问答记录”排版：左侧窄栏标注说话方，右侧正文。
 * AI 的问题是正文主体，用户回答以蓝色竖线标出。
 */
export default function MessageList({ messages, loading }: MessageListProps) {
  return (
    <ol className="mx-auto max-w-3xl py-6">
      {messages.map((message, index) => {
        const isUser = message.role === 'user' || message.role === 'human';
        return (
          <li
            key={index}
            className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3 border-b border-hair py-5 last:border-b-0 sm:grid-cols-[4.5rem_minmax(0,1fr)]"
          >
            <div className={`pt-0.5 text-xs font-medium ${isUser ? 'text-primary-700' : 'text-slate-500'}`}>
              {isUser ? '你' : 'ReqFlow'}
            </div>

            {isUser ? (
              <p className="whitespace-pre-wrap border-l-2 border-primary-600 pl-3 text-[15px] leading-relaxed text-ink">
                {message.content}
              </p>
            ) : (
              <ReactMarkdown
                className="prose prose-sm max-w-none text-[15px] leading-relaxed text-ink"
                components={{
                  p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2.5 list-disc pl-5 marker:text-slate-400">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-2.5 list-decimal pl-5 marker:text-primary-600">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  code: ({ children }) => (
                    <code className="rounded-sm bg-slate-100 px-1.5 py-0.5 font-mono text-[13px]">{children}</code>
                  ),
                  pre: ({ children }) => (
                    <pre className="overflow-x-auto rounded border border-hair bg-slate-50 p-3 font-mono text-[13px]">
                      {children}
                    </pre>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </li>
        );
      })}

      {loading && (
        <li className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3 py-5 sm:grid-cols-[4.5rem_minmax(0,1fr)]" role="status">
          <div className="pt-0.5 text-xs font-medium text-slate-500">ReqFlow</div>
          <div className="flex h-6 items-center gap-1.5" aria-label="正在回复">
            {[0, 0.15, 0.3].map((delay) => (
              <span
                key={delay}
                className="h-1.5 w-4 animate-pulse bg-primary-300"
                style={{ animationDelay: `${delay}s` }}
              />
            ))}
          </div>
        </li>
      )}
    </ol>
  );
}
