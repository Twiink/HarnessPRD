import axios from 'axios';
import type {
  ContextUsage,
  GeneratePrdStreamResult,
  PRDResponse,
  PrdReviewResult,
  QuestionsConfig,
  Message,
  RunSummary,
} from '../types';

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

export class StreamError extends Error {
  code?: string;
  request_id?: string;

  constructor(message: string, code?: string, request_id?: string) {
    super(message);
    this.name = 'StreamError';
    this.code = code;
    this.request_id = request_id;
  }
}

export type StreamHandlers = {
  onPhase?: (phase: string) => void;
  onReview?: (review: PrdReviewResult) => void;
  onRunSummary?: (summary: RunSummary) => void;
  onContextUsage?: (usage: ContextUsage) => void;
};

function parseHttpErrorPayload(payload: unknown): StreamError {
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const detail = record.detail;
    if (detail && typeof detail === 'object') {
      const detailRecord = detail as Record<string, unknown>;
      if (detailRecord.code === 'TOKEN_BUDGET_EXCEEDED') {
        return new StreamError(
          String(detailRecord.message || '上下文过长，请缩短对话或结束澄清'),
          'TOKEN_BUDGET_EXCEEDED',
          typeof detailRecord.request_id === 'string' ? detailRecord.request_id : undefined,
        );
      }
      if (typeof detailRecord.message === 'string') {
        return new StreamError(
          detailRecord.message,
          typeof detailRecord.code === 'string' ? detailRecord.code : undefined,
          typeof detailRecord.request_id === 'string' ? detailRecord.request_id : undefined,
        );
      }
    }
    if (typeof record.message === 'string') {
      return new StreamError(
        record.message,
        typeof record.code === 'string' ? record.code : undefined,
        typeof record.request_id === 'string' ? record.request_id : undefined,
      );
    }
    if (typeof detail === 'string') {
      return new StreamError(detail);
    }
  }
  return new StreamError('Request failed');
}

async function readStream(
  url: string,
  body: object,
  onChunk: (text: string) => void,
  handlers?: StreamHandlers,
): Promise<any> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw parseHttpErrorPayload(err);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: any = null;
  let streamError: StreamError | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') break;

      const event = JSON.parse(data);
      if (event.type === 'error') {
        streamError = new StreamError(
          event.message || 'Request failed',
          event.code,
          event.request_id,
        );
        if (event.context_usage) {
          handlers?.onContextUsage?.(event.context_usage);
        }
        continue;
      }
      if (event.type === 'chunk' || event.type === 'text_delta') {
        onChunk(event.content);
      } else if (event.type === 'phase') {
        handlers?.onPhase?.(event.phase);
      } else if (event.type === 'review') {
        handlers?.onReview?.(event.content);
      } else if (event.type === 'run_summary') {
        const { type: _type, ...summary } = event;
        handlers?.onRunSummary?.(summary as RunSummary);
      } else if (event.type === 'done') {
        result = event;
        if (event.context_usage) {
          handlers?.onContextUsage?.(event.context_usage);
        }
      }
    }
  }

  if (streamError) throw streamError;
  return result;
}

// ── 对话 API ─────────────────────────────────────────────────────────────────

export const conversationApi = {
  async getQuestions(): Promise<QuestionsConfig> {
    const res = await apiClient.get<QuestionsConfig>('/conversation/questions');
    return res.data;
  },

  /** 开始对话 — 流式，onChunk 每次收到文字片段时回调 */
  async startConversationStream(
    initialInput: string,
    formData: Record<string, string>,
    systemPromptOverride: string | undefined,
    onChunk: (text: string) => void,
    handlers?: Pick<StreamHandlers, 'onContextUsage' | 'onRunSummary'>,
  ): Promise<{ conversation_id: string; messages: Message[] }> {
    return readStream(
      '/api/conversation/start-stream',
      { initial_input: initialInput, form_data: formData, system_prompt_override: systemPromptOverride },
      onChunk,
      handlers,
    );
  },

  /** 继续对话 — 流式 */
  async continueConversationStream(
    conversationId: string,
    messages: Message[],
    userInput: string,
    onChunk: (text: string) => void,
    handlers?: Pick<StreamHandlers, 'onContextUsage' | 'onRunSummary'>,
  ): Promise<{ conversation_id: string; messages: Message[] }> {
    return readStream(
      '/api/conversation/continue-stream',
      { conversation_id: conversationId, messages, user_input: userInput },
      onChunk,
      handlers,
    );
  },

  async generatePRD(conversationMessages: Message[]): Promise<PRDResponse> {
    const res = await apiClient.post<PRDResponse>('/conversation/generate-prd', {
      conversation_messages: conversationMessages,
    });
    return res.data;
  },

  /** 生成 PRD — 流式 */
  async generatePrdStream(
    conversationMessages: Message[],
    onChunk: (text: string) => void,
    handlers?: StreamHandlers,
  ): Promise<GeneratePrdStreamResult> {
    return readStream(
      '/api/conversation/generate-prd-stream',
      { conversation_messages: conversationMessages },
      onChunk,
      handlers,
    );
  },

  async generatePrdFromSummaryStream(
    requirementsSummary: Record<string, unknown>,
    conversationMessages: Message[],
    onChunk: (text: string) => void,
    handlers?: StreamHandlers,
  ): Promise<GeneratePrdStreamResult> {
    return readStream(
      '/api/conversation/generate-prd-from-summary-stream',
      { requirements_summary: requirementsSummary, conversation_messages: conversationMessages },
      onChunk,
      handlers,
    );
  },

  async syncSummaryFromConversation(
    requirementsSummary: Record<string, unknown>,
    conversationMessages: Message[],
  ): Promise<{ requirements_summary: Record<string, unknown>; status: string }> {
    const res = await apiClient.post('/conversation/sync-summary-from-conversation', {
      requirements_summary: requirementsSummary,
      conversation_messages: conversationMessages,
    });
    return res.data;
  },

  /** 生成接口文档 — 流式 */
  async generateApiDocsStream(
    prdContent: string,
    conversationMessages: Message[],
    onChunk: (text: string) => void,
    handlers?: StreamHandlers,
  ): Promise<void> {
    await readStream(
      '/api/conversation/generate-api-docs-stream',
      { prd_content: prdContent, conversation_messages: conversationMessages },
      onChunk,
      handlers,
    );
  },

  /** 生成 AI 提示词套件 — 流式 */
  async generatePromptsStream(
    prdContent: string,
    apiDocsContent: string,
    onChunk: (text: string) => void,
    handlers?: StreamHandlers,
  ): Promise<void> {
    await readStream(
      '/api/conversation/generate-prompts-stream',
      { prd_content: prdContent, api_docs_content: apiDocsContent },
      onChunk,
      handlers,
    );
  },

  /** 优化文档内容 — 流式 */
  async optimizeDocumentStream(
    docType: string,
    currentContent: string,
    instruction: string,
    context: string,
    onChunk: (text: string) => void,
    handlers?: StreamHandlers,
  ): Promise<void> {
    await readStream(
      '/api/conversation/optimize-document-stream',
      { doc_type: docType, current_content: currentContent, instruction, context },
      onChunk,
      handlers,
    );
  },
};
