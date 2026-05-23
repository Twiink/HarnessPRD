import { useState, useEffect, useRef, useMemo } from 'react';
import { Sparkles, FileText, MessageSquare, ClipboardList, Code2, Download, CheckCircle2 } from 'lucide-react';
import MessageList from './components/MessageList';
import ChatInput from './components/ChatInput';
import FormStep from './components/FormStep';
import DocumentReview from './components/DocumentReview';
import { conversationApi } from './services/api';
import type {
  Message,
  QuestionsConfig,
  ViewState,
  DocType,
  PrdGenerationStage,
  PrdReviewResult,
} from './types';

// ── 进度步骤 ──────────────────────────────────────────────────────────────────

const STEPS = [
  { id: 'form',         label: '描述产品',  icon: ClipboardList },
  { id: 'chatting',     label: 'AI 对话',   icon: MessageSquare },
  { id: 'review-prd',   label: 'PRD',       icon: FileText },
  { id: 'review-api-docs', label: '接口文档', icon: Code2 },
  { id: 'review-prompts',  label: '提示词',  icon: Sparkles },
] as const;

const STEP_INDEX: Record<ViewState, number> = {
  'form': 0,
  'chatting': 1,
  'generating-prd': 2,
  'review-prd': 2,
  'generating-api-docs': 3,
  'review-api-docs': 3,
  'generating-prompts': 4,
  'review-prompts': 4,
  'done': 4,
};

// ── localStorage ─────────────────────────────────────────────────────────────

const SESSION_KEY = 'vibecoding_session';

type SessionData = {
  formData?: Record<string, string>;
  messages?: Message[];
  conversationId?: string;
  viewState?: ViewState;
  prdContent?: string;
  apiDocsContent?: string;
  promptsContent?: string;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return `${fallback}：${error.message}`;
  }
  return fallback;
}

function saveSession(data: Partial<SessionData>) {
  try {
    const prev: SessionData = JSON.parse(localStorage.getItem(SESSION_KEY) || '{}');
    localStorage.setItem(SESSION_KEY, JSON.stringify({ ...prev, ...data }));
  } catch {}
}

function loadSession(): SessionData | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s: SessionData = JSON.parse(raw);
    // 降级 generating-* 状态，避免恢复到半生成状态
    if (s.viewState?.startsWith('generating-')) {
      const fallback: Record<string, ViewState> = {
        'generating-prd': s.prdContent ? 'review-prd' : 'chatting',
        'generating-api-docs': s.apiDocsContent ? 'review-api-docs' : 'review-prd',
        'generating-prompts': s.promptsContent ? 'review-prompts' : 'review-api-docs',
      };
      s.viewState = fallback[s.viewState!] ?? 'chatting';
    }
    return s;
  } catch {
    return null;
  }
}

// ── 下载工具 ──────────────────────────────────────────────────────────────────

function downloadFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [viewState, setViewState] = useState<ViewState>('form');
  const [questions, setQuestions] = useState<QuestionsConfig>({ base_questions: [], advanced_questions: [] });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 对话消息
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState('');

  // 文档内容
  const [prdContent, setPrdContent] = useState('');
  const [apiDocsContent, setApiDocsContent] = useState('');
  const [promptsContent, setPromptsContent] = useState('');

  // 流式状态（通用：聊天/生成/优化共用 streamingContent）
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);   // 聊天流式
  const [isGenerating, setIsGenerating] = useState(false); // 文档优化流式
  const [prdGenerationStage, setPrdGenerationStage] = useState<PrdGenerationStage>('idle');
  const [prdReviewResult, setPrdReviewResult] = useState<PrdReviewResult | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── 初始化 ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    conversationApi.getQuestions().then(setQuestions).catch(console.error);
    const session = loadSession();
    if (session) {
      if (session.formData) setFormData(session.formData);
      if (session.messages?.length) setMessages(session.messages);
      if (session.conversationId) setConversationId(session.conversationId);
      if (session.viewState) setViewState(session.viewState);
      if (session.prdContent) setPrdContent(session.prdContent);
      if (session.apiDocsContent) setApiDocsContent(session.apiDocsContent);
      if (session.promptsContent) setPromptsContent(session.promptsContent);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // ── 展示用消息（过滤 system 和首条上下文 human）────────────────────────────

  const displayMessages = useMemo(() => {
    const visible = messages.filter((m) => m.role !== 'system').slice(1);
    if (streamingContent && isStreaming) {
      return [...visible, { role: 'ai' as const, content: streamingContent }];
    }
    return visible;
  }, [messages, streamingContent, isStreaming]);

  const userMessageCount = useMemo(
    () => messages.filter((m) => m.role === 'human' || m.role === 'user').length,
    [messages]
  );
  const canGeneratePrd = userMessageCount >= 2;

  const productName = formData['product_name'] || '产品';
  const prdGenerationStatusText = useMemo(() => {
    if (prdGenerationStage === 'writing') return 'Writer Agent 正在起草...';
    if (prdGenerationStage === 'reviewing') return 'Review Agent 正在审查...';
    if (prdGenerationStage === 'rewriting') return 'Writer Agent 正在修订...';
    return '生成中...';
  }, [prdGenerationStage]);

  // ── 表单 ───────────────────────────────────────────────────────────────────

  const handleFormChange = (id: string, value: string) => {
    const next = { ...formData, [id]: value };
    setFormData(next);
    saveSession({ formData: next });
  };

  // ── 开始对话 ───────────────────────────────────────────────────────────────

  const handleStartConversation = async () => {
    setIsStreaming(true);
    setStreamingContent('');
    setMessages([]);
    setViewState('chatting');

    let accumulated = '';
    try {
      const result = await conversationApi.startConversationStream('', formData, undefined, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      setMessages(result.messages);
      setConversationId(result.conversation_id);
      saveSession({ messages: result.messages, conversationId: result.conversation_id, viewState: 'chatting', formData });
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '启动对话失败，请检查后端配置'));
      setViewState('form');
    } finally {
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  // ── 继续对话 ───────────────────────────────────────────────────────────────

  const handleSendMessage = async (userInput: string) => {
    if (isStreaming || isGenerating) return;

    const withUser: Message[] = [...messages, { role: 'human', content: userInput }];
    setMessages(withUser);
    setIsStreaming(true);
    setStreamingContent('');

    let accumulated = '';
    try {
      const result = await conversationApi.continueConversationStream(
        conversationId, messages, userInput,
        (chunk) => { accumulated += chunk; setStreamingContent(accumulated); }
      );
      setMessages(result.messages);
      saveSession({ messages: result.messages });
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '发送消息失败'));
      setMessages(messages);
    } finally {
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  // ── 生成 PRD（流式） ────────────────────────────────────────────────────────

  const handleGeneratePRD = async () => {
    setPrdContent('');
    setPrdReviewResult(null);
    setViewState('generating-prd');
    setStreamingContent('');
    setPrdGenerationStage('writing');

    let accumulated = '';
    try {
      const result = await conversationApi.generatePrdStream(
        messages,
        (chunk) => {
          accumulated += chunk;
          setStreamingContent(accumulated);
        },
        {
          onPhase: (phase) => {
            if (phase === 'writer_started') {
              accumulated = '';
              setPrdGenerationStage('writing');
              setStreamingContent('');
            } else if (phase === 'review_started') {
              setPrdGenerationStage('reviewing');
            } else if (phase === 'rewrite_started') {
              accumulated = '';
              setPrdGenerationStage('rewriting');
              setStreamingContent('');
            }
          },
          onReview: (review) => {
            setPrdReviewResult(review);
          },
        }
      );
      setPrdContent(result.final_prd);
      setPrdReviewResult(result.review);
      setPrdGenerationStage('done');
      saveSession({ prdContent: result.final_prd, viewState: 'review-prd' });
      setViewState('review-prd');
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '生成 PRD 失败'));
      setPrdGenerationStage('error');
      setViewState('chatting');
    } finally {
      setStreamingContent('');
    }
  };

  // ── 生成接口文档（流式） ────────────────────────────────────────────────────

  const handleGenerateApiDocs = async () => {
    setApiDocsContent('');
    setViewState('generating-api-docs');
    setStreamingContent('');

    let accumulated = '';
    try {
      await conversationApi.generateApiDocsStream(prdContent, messages, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      setApiDocsContent(accumulated);
      saveSession({ apiDocsContent: accumulated, viewState: 'review-api-docs' });
      setViewState('review-api-docs');
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '生成接口文档失败'));
      setViewState('review-prd');
    } finally {
      setStreamingContent('');
    }
  };

  // ── 生成提示词（流式） ──────────────────────────────────────────────────────

  const handleGeneratePrompts = async (skipApiDocs: boolean) => {
    setPromptsContent('');
    setViewState('generating-prompts');
    setStreamingContent('');

    let accumulated = '';
    try {
      await conversationApi.generatePromptsStream(
        prdContent,
        skipApiDocs ? '' : apiDocsContent,
        (chunk) => { accumulated += chunk; setStreamingContent(accumulated); }
      );
      setPromptsContent(accumulated);
      saveSession({ promptsContent: accumulated, viewState: 'review-prompts' });
      setViewState('review-prompts');
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '生成提示词失败'));
      setViewState(skipApiDocs ? 'review-prd' : 'review-api-docs');
    } finally {
      setStreamingContent('');
    }
  };

  // ── 优化文档（流式替换） ────────────────────────────────────────────────────

  const handleOptimizeDocument = async (
    docType: DocType,
    currentContent: string,
    instruction: string,
    context: string
  ) => {
    setIsGenerating(true);
    setStreamingContent('');

    let accumulated = '';
    try {
      await conversationApi.optimizeDocumentStream(docType, currentContent, instruction, context, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      if (docType === 'prd') {
        setPrdContent(accumulated);
        saveSession({ prdContent: accumulated });
      } else if (docType === 'api-docs') {
        setApiDocsContent(accumulated);
        saveSession({ apiDocsContent: accumulated });
      } else if (docType === 'prompts') {
        setPromptsContent(accumulated);
        saveSession({ promptsContent: accumulated });
      }
    } catch (err) {
      console.error(err);
      alert(getErrorMessage(err, '优化失败，请重试'));
    } finally {
      setStreamingContent('');
      setIsGenerating(false);
    }
  };

  // ── 结束任务 ────────────────────────────────────────────────────────────────

  const handleEndTask = () => {
    setViewState('done');
    saveSession({ viewState: 'done' });
  };

  // ── 重新开始 ────────────────────────────────────────────────────────────────

  const handleRestart = () => {
    localStorage.removeItem(SESSION_KEY);
    setViewState('form');
    setMessages([]);
    setConversationId('');
    setPrdContent('');
    setApiDocsContent('');
    setPromptsContent('');
    setFormData({});
    setStreamingContent('');
  };

  // ── 进度步骤 ────────────────────────────────────────────────────────────────

  const currentStepIdx = STEP_INDEX[viewState] ?? 0;

  // ── 渲染 ─────────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex-shrink-0">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gray-900">Vibe Coding</span>
          </div>

          <div className="hidden sm:flex items-center gap-1">
            {STEPS.map((step, idx) => {
              const Icon = step.icon;
              const isActive = currentStepIdx === idx;
              const isDone = currentStepIdx > idx;
              return (
                <div key={step.id} className="flex items-center">
                  <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    isActive ? 'bg-primary-100 text-primary-700' : isDone ? 'text-green-600' : 'text-gray-400'
                  }`}>
                    <Icon className="w-3.5 h-3.5" />
                    {step.label}
                  </div>
                  {idx < STEPS.length - 1 && (
                    <div className={`w-6 h-px mx-1 ${isDone ? 'bg-green-400' : 'bg-gray-200'}`} />
                  )}
                </div>
              );
            })}
          </div>

          <div className="w-20" />
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-hidden">

        {/* 表单阶段 */}
        {viewState === 'form' && (
          <FormStep
            questions={questions}
            formData={formData}
            onChange={handleFormChange}
            showAdvanced={showAdvanced}
            onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
            onSubmit={handleStartConversation}
            loading={isStreaming}
          />
        )}

        {/* 对话阶段 */}
        {viewState === 'chatting' && (
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-y-auto">
              <MessageList
                messages={displayMessages}
                loading={isStreaming && streamingContent === ''}
              />
              <div ref={messagesEndRef} />
            </div>
            <div className="border-t border-gray-100 bg-white px-4 pt-3 pb-4 flex-shrink-0">
              <div className="max-w-4xl mx-auto space-y-2">
                <ChatInput onSend={handleSendMessage} loading={isStreaming} />
                {canGeneratePrd && (
                  <div className="flex justify-end">
                    <button
                      onClick={handleGeneratePRD}
                      disabled={isStreaming}
                      className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-lg text-xs font-medium hover:from-primary-700 hover:to-primary-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      生成 PRD
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* PRD 生成中 */}
        {viewState === 'generating-prd' && (
          <DocumentReview
            title="产品需求文档（PRD）"
            content=""
            streamingContent={streamingContent}
            isGeneratingPhase={true}
            isGenerating={true}
            generationStatusText={prdGenerationStatusText}
            reviewResult={prdReviewResult}
            actions={[]}
            onSaveEdit={() => {}}
            onOptimize={() => {}}
          />
        )}

        {/* PRD 审核 */}
        {viewState === 'review-prd' && (
          <DocumentReview
            title="产品需求文档（PRD）"
            content={prdContent}
            downloadFilename={`${productName}-PRD`}
            streamingContent={isGenerating ? streamingContent : undefined}
            isGenerating={isGenerating}
            reviewResult={prdReviewResult}
            actions={[
              {
                label: '返回对话',
                variant: 'secondary',
                onClick: () => setViewState('chatting'),
                disabled: isGenerating,
              },
              {
                label: '结束任务',
                variant: 'ghost',
                onClick: handleEndTask,
                disabled: isGenerating,
              },
              {
                label: '直接生成提示词',
                variant: 'secondary',
                onClick: () => handleGeneratePrompts(true),
                disabled: isGenerating,
              },
              {
                label: '生成接口文档 →',
                variant: 'primary',
                onClick: handleGenerateApiDocs,
                disabled: isGenerating,
              },
            ]}
            onSaveEdit={(c) => { setPrdContent(c); saveSession({ prdContent: c }); }}
            onOptimize={(inst) => handleOptimizeDocument('prd', prdContent, inst, '')}
          />
        )}

        {/* 接口文档生成中 */}
        {viewState === 'generating-api-docs' && (
          <DocumentReview
            title="接口文档"
            content=""
            streamingContent={streamingContent}
            isGeneratingPhase={true}
            isGenerating={true}
            actions={[]}
            onSaveEdit={() => {}}
            onOptimize={() => {}}
          />
        )}

        {/* 接口文档审核 */}
        {viewState === 'review-api-docs' && (
          <DocumentReview
            title="接口文档"
            content={apiDocsContent}
            downloadFilename={`${productName}-API-Docs`}
            streamingContent={isGenerating ? streamingContent : undefined}
            isGenerating={isGenerating}

            actions={[
              {
                label: '结束任务',
                variant: 'ghost',
                onClick: handleEndTask,
                disabled: isGenerating,
              },
              {
                label: '生成提示词 →',
                variant: 'primary',
                onClick: () => handleGeneratePrompts(false),
                disabled: isGenerating,
              },
            ]}
            onSaveEdit={(c) => { setApiDocsContent(c); saveSession({ apiDocsContent: c }); }}
            onOptimize={(inst) => handleOptimizeDocument('api-docs', apiDocsContent, inst, prdContent)}
          />
        )}

        {/* 提示词生成中 */}
        {viewState === 'generating-prompts' && (
          <DocumentReview
            title="AI 提示词套件"
            content=""
            streamingContent={streamingContent}
            isGeneratingPhase={true}
            isGenerating={true}
            actions={[]}
            onSaveEdit={() => {}}
            onOptimize={() => {}}
          />
        )}

        {/* 提示词审核 */}
        {viewState === 'review-prompts' && (
          <DocumentReview
            title="AI 提示词套件"
            content={promptsContent}
            downloadFilename={`${productName}-Prompts`}
            streamingContent={isGenerating ? streamingContent : undefined}
            isGenerating={isGenerating}
            actions={[
              {
                label: '完成，下载全部',
                variant: 'primary',
                onClick: handleEndTask,
                disabled: isGenerating,
              },
            ]}
            onSaveEdit={(c) => { setPromptsContent(c); saveSession({ promptsContent: c }); }}
            onOptimize={(inst) =>
              handleOptimizeDocument('prompts', promptsContent, inst, `${prdContent}\n\n${apiDocsContent}`)
            }
          />
        )}

        {/* 完成总结页 */}
        {viewState === 'done' && (
          <div className="h-full flex items-center justify-center">
            <div className="max-w-lg w-full mx-auto px-6">
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle2 className="w-8 h-8 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">全部完成！</h2>
                <p className="text-gray-500">以下文档已生成，点击下载保存</p>
              </div>

              <div className="space-y-3 mb-8">
                {prdContent && (
                  <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-primary-500" />
                      <div>
                        <p className="font-medium text-gray-900">产品需求文档（PRD）</p>
                        <p className="text-xs text-gray-400">{productName}-PRD.md</p>
                      </div>
                    </div>
                    <button
                      onClick={() => downloadFile(`${productName}-PRD.md`, prdContent)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      下载
                    </button>
                  </div>
                )}

                {apiDocsContent && (
                  <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
                    <div className="flex items-center gap-3">
                      <Code2 className="w-5 h-5 text-blue-500" />
                      <div>
                        <p className="font-medium text-gray-900">接口文档</p>
                        <p className="text-xs text-gray-400">{productName}-API-Docs.md</p>
                      </div>
                    </div>
                    <button
                      onClick={() => downloadFile(`${productName}-API-Docs.md`, apiDocsContent)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      下载
                    </button>
                  </div>
                )}

                {promptsContent && (
                  <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
                    <div className="flex items-center gap-3">
                      <Sparkles className="w-5 h-5 text-purple-500" />
                      <div>
                        <p className="font-medium text-gray-900">AI 提示词套件</p>
                        <p className="text-xs text-gray-400">{productName}-Prompts.md</p>
                      </div>
                    </div>
                    <button
                      onClick={() => downloadFile(`${productName}-Prompts.md`, promptsContent)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      下载
                    </button>
                  </div>
                )}
              </div>

              <div className="text-center">
                <button
                  onClick={handleRestart}
                  className="px-6 py-2.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  重新开始新项目
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
