import axios from 'axios';
import type {
  GeneratePrdStreamResult,
  PRDResponse,
  PrdReviewResult,
  QuestionsConfig,
  Message,
  RagHit,
} from '../types';

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// ── SSE 流式读取工具 ─────────────────────────────────────────────────────────

async function readStream(
  url: string,
  body: object,
  onChunk: (text: string) => void,
  handlers?: {
    onPhase?: (phase: string) => void;
    onReview?: (review: PrdReviewResult) => void;
  }
): Promise<any> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: any = null;

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
      if (event.type === 'error') throw new Error(event.message);
      if (event.type === 'chunk' || event.type === 'text_delta') onChunk(event.content);
      else if (event.type === 'phase') handlers?.onPhase?.(event.phase);
      else if (event.type === 'review') handlers?.onReview?.(event.content);
      else if (event.type === 'done') result = event;
    }
  }

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
    onChunk: (text: string) => void
  ): Promise<{ conversation_id: string; messages: Message[] }> {
    return readStream(
      '/api/conversation/start-stream',
      { initial_input: initialInput, form_data: formData, system_prompt_override: systemPromptOverride },
      onChunk
    );
  },

  /** 继续对话 — 流式 */
  async continueConversationStream(
    conversationId: string,
    messages: Message[],
    userInput: string,
    onChunk: (text: string) => void
  ): Promise<{ conversation_id: string; messages: Message[] }> {
    return readStream(
      '/api/conversation/continue-stream',
      { conversation_id: conversationId, messages, user_input: userInput },
      onChunk
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
    handlers?: {
      onPhase?: (phase: string) => void;
      onReview?: (review: PrdReviewResult) => void;
    }
  ): Promise<GeneratePrdStreamResult> {
    return readStream(
      '/api/conversation/generate-prd-stream',
      { conversation_messages: conversationMessages },
      onChunk,
      handlers
    );
  },

  async generatePrdFromSummaryStream(
    requirementsSummary: Record<string, unknown>,
    conversationMessages: Message[],
    onChunk: (text: string) => void,
    handlers?: {
      onPhase?: (phase: string) => void;
      onReview?: (review: PrdReviewResult) => void;
    }
  ): Promise<GeneratePrdStreamResult> {
    return readStream(
      '/api/conversation/generate-prd-from-summary-stream',
      { requirements_summary: requirementsSummary, conversation_messages: conversationMessages },
      onChunk,
      handlers
    );
  },

  async syncSummaryFromConversation(
    requirementsSummary: Record<string, unknown>,
    conversationMessages: Message[]
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
    onChunk: (text: string) => void
  ): Promise<void> {
    await readStream(
      '/api/conversation/generate-api-docs-stream',
      { prd_content: prdContent, conversation_messages: conversationMessages },
      onChunk
    );
  },

  async retrieveApiDocsRag(
    prdContent: string,
    conversationMessages: Message[]
  ): Promise<{ status: string; hits: RagHit[] }> {
    const res = await apiClient.post('/conversation/retrieve-api-docs-rag', {
      prd_content: prdContent,
      conversation_messages: conversationMessages,
    });
    return res.data;
  },

  /** 生成 AI 提示词套件 — 流式 */
  async generatePromptsStream(
    prdContent: string,
    apiDocsContent: string,
    onChunk: (text: string) => void
  ): Promise<void> {
    await readStream(
      '/api/conversation/generate-prompts-stream',
      { prd_content: prdContent, api_docs_content: apiDocsContent },
      onChunk
    );
  },

  /** 优化文档内容 — 流式 */
  async optimizeDocumentStream(
    docType: string,
    currentContent: string,
    instruction: string,
    context: string,
    onChunk: (text: string) => void
  ): Promise<void> {
    await readStream(
      '/api/conversation/optimize-document-stream',
      { doc_type: docType, current_content: currentContent, instruction, context },
      onChunk
    );
  },
};
