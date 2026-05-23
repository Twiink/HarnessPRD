import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, MessageSquare, Sparkles } from 'lucide-react';
import MessageList from './components/MessageList';
import ChatInput from './components/ChatInput';
import DocumentReview from './components/DocumentReview';
import SummaryDiffPanel from './components/SummaryDiffPanel';
import type { SummaryDiffItem } from './types/summaryDiff';
import { conversationApi } from './services/api';
import type { DocType, Message, PrdGenerationStage, PrdReviewResult, RagHit } from './types';

type V2ViewState =
  | 'form'
  | 'chatting'
  | 'generating-prd'
  | 'review-prd'
  | 'generating-api-docs'
  | 'review-api-docs'
  | 'generating-prompts'
  | 'review-prompts';
type EntryMode = 'structured' | 'prd' | 'prompts';

type RequirementsSummary = {
  product_name: string;
  product_goal: string;
  target_users: string[];
  platform: string;
  mvp_features: Array<{
    name: string;
    description: string;
    user_value: string;
  }>;
  v2_features?: string[];
  ui_pages?: Array<{
    name: string;
    modules?: string[];
    notes?: string;
  }>;
  interaction_notes?: string[];
  design_requirements?: {
    theme?: string;
    responsive?: boolean;
  };
  technical_constraints?: {
    auth?: string;
    database?: string;
    frontend?: string;
    backend?: string;
    deployment?: string;
    llm_usage?: string;
  };
  non_functional_requirements?: {
    security?: string[];
    performance?: string[];
    usability?: string[];
  };
  in_scope?: string[];
  out_of_scope?: string[];
};

type StructuredFormData = {
  product_name: string;
  product_goal: string;
  target_users: string;
  platform: string;
  mvp_features: string;
  v2_features: string;
  ui_pages: string;
  interaction_notes: string;
  design_theme: string;
  responsive: string;
  auth: string;
  database: string;
  frontend: string;
  backend: string;
  deployment: string;
  llm_usage: string;
  security_requirements: string;
  performance_requirements: string;
  usability_requirements: string;
  in_scope: string;
  out_of_scope: string;
};

type StructuredFormErrors = Partial<Record<keyof StructuredFormData, string>>;

type V2SessionData = {
  viewState?: V2ViewState;
  entryMode?: EntryMode;
  formData?: StructuredFormData;
  requirementsSummary?: RequirementsSummary | null;
  pendingSummary?: RequirementsSummary | null;
  messages?: Message[];
  conversationId?: string;
  prdContent?: string;
  apiDocsContent?: string;
  promptsContent?: string;
  manualPrdInput?: string;
  manualApiDocsInput?: string;
  ragHits?: RagHit[];
  pendingApiDocsPrd?: string;
  showJsonPreview?: boolean;
  prdReviewResult?: PrdReviewResult | null;
};

const V2_SESSION_KEY = 'vibecoding_v2_session';
/** 全站内容区统一宽度，与顶栏对齐 */
const V2_PAGE_CLASS = 'mx-auto w-full max-w-6xl px-6';

const CLARIFICATION_SYSTEM_PROMPT = `你是一位资深产品经理，正在帮助用户补齐一份已经结构化过的产品需求摘要。

你的任务边界：
1. 只做需求澄清、补充确认和纠偏
2. 每次只聚焦 1-3 个最需要确认的问题
3. 优先识别会影响 PRD 结构化输出的缺失项或歧义项
4. 可以总结当前已确认内容，但总结必须简短

严格限制：
1. 不要生成 PRD
2. 不要输出完整文档、完整模板、接口文档或大段结构化产物
3. 不要说“我来为你生成 PRD”或直接进入文档撰写
4. 在信息已经足够时，只需明确提示用户“如果没有更多补充，可以点击生成 PRD”

使用中文回复。`;

const DEFAULT_FORM: StructuredFormData = {
  product_name: '',
  product_goal: '',
  target_users: '',
  platform: '网页应用（Web App）',
  mvp_features: '',
  v2_features: '',
  ui_pages: '',
  interaction_notes: '',
  design_theme: '',
  responsive: '需要',
  auth: '待确认',
  database: '待确认',
  frontend: '',
  backend: '',
  deployment: '',
  llm_usage: '',
  security_requirements: '',
  performance_requirements: '',
  usability_requirements: '',
  in_scope: '',
  out_of_scope: '',
};

const EXAMPLE_FORM: StructuredFormData = {
  product_name: '朋友圈文案助手',
  product_goal: '帮助运营人员快速生成高质量朋友圈文案，降低内容创作门槛。',
  target_users: '微商\n销售\n自媒体从业者\n小企业主',
  platform: '网页应用（Web App）',
  mvp_features:
    '场景分类选择｜提供 7 个预设场景标签供用户单选｜降低用户思考成本，快速确定文案方向\n' +
    '场景自由描述｜允许用户补充具体场景描述，最多 200 字｜支持个性化生成，提高结果准确性\n' +
    '场景校验逻辑｜场景分类和场景描述至少填写一项｜保证模型获得足够上下文\n' +
    '风格选择｜提供 6 个预设风格供用户单选｜控制输出文案调性\n' +
    '字数范围选择｜提供 4 档字数区间供用户单选｜适配不同内容长度需求\n' +
    '参考示例输入｜支持填写最多 3 条参考文案，每条最多 500 字｜提升生成结果与用户偏好的贴合度\n' +
    '一次生成 3 条文案｜基于当前条件返回 3 条不同文案｜提供更多可选结果\n' +
    '一键复制｜每条文案提供复制按钮并显示成功提示｜缩短从生成到发布的路径\n' +
    '换一批｜保留原条件重新生成 3 条文案｜快速获取替代结果\n' +
    '返回修改条件｜支持回到输入页修改参数并保留原输入｜便于快速迭代优化',
  v2_features: '历史记录\n收藏功能\n文案模板库\n批量生成\n配图建议\n多语言支持',
  ui_pages:
    '输入页｜场景分类,场景描述,风格选择,字数范围选择,参考示例输入,生成按钮｜主输入视图\n' +
    '结果页｜结果卡片,复制按钮,换一批按钮,修改条件按钮｜展示生成结果',
  interaction_notes: '采用单页应用形式，通过输入页和结果页两个视图切换完成主流程\n结果页支持基于原参数重新生成\n返回修改条件时保留原输入内容',
  design_theme: '科技感暗色',
  responsive: '需要',
  auth: '不需要登录',
  database: '不需要数据库',
  frontend: 'React + TypeScript',
  backend: 'Serverless Function',
  deployment: 'Vercel + Serverless Function',
  llm_usage: '调用大语言模型 API，一次生成 3 条朋友圈文案。',
  security_requirements: 'API Key 仅存储在服务端环境变量中\n前端做输入长度限制与基础 XSS 防护\n增加简单频率限制，例如每分钟最多 10 次生成',
  performance_requirements: '页面首次加载时间不超过 2 秒\nAI 文案生成响应时间不超过 10 秒',
  usability_requirements: '表单校验需提供实时反馈\n生成失败时保留用户已填写内容\n移动端点击区域不小于 44px\n兼容主流浏览器',
  in_scope: '单页 Web 应用开发\n输入页与结果页视图切换\n场景分类与自由描述输入\n风格和字数范围选择\n参考示例输入\n生成 3 条文案\n复制、换一批、返回修改条件\n响应式适配\nServerless Function 中转模型调用',
  out_of_scope: '用户登录注册\n数据库存储与历史记录\n收藏功能\n模板库\n批量生成\n配图建议\n多语言支持\n后台管理\n原生 App 与小程序',
};

function parseList(raw: string): string[] {
  return raw
    .split('\n')
    .map((line) => line.trim().replace(/^[\d\-\*\.\、\s]+/, ''))
    .filter(Boolean);
}

function parseCommaList(raw: string): string[] {
  return raw
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseMvpFeatures(raw: string) {
  return parseList(raw).map((line) => {
    const parts = line.split(/[|｜]/).map((part) => part.trim());
    return {
      name: parts[0] || '待确认',
      description: parts[1] || parts[0] || '待确认',
      user_value: parts[2] || '待确认',
    };
  });
}

function parsePages(raw: string) {
  return parseList(raw).map((line) => {
    const parts = line.split(/[|｜]/).map((part) => part.trim());
    return {
      name: parts[0] || '待确认',
      modules: parts[1] ? parseCommaList(parts[1]) : [],
      notes: parts[2] || '',
    };
  });
}

function buildRequirementsSummary(formData: StructuredFormData): RequirementsSummary {
  return {
    product_name: formData.product_name.trim(),
    product_goal: formData.product_goal.trim(),
    target_users: parseList(formData.target_users),
    platform: formData.platform.trim(),
    mvp_features: parseMvpFeatures(formData.mvp_features),
    v2_features: parseList(formData.v2_features),
    ui_pages: parsePages(formData.ui_pages),
    interaction_notes: parseList(formData.interaction_notes),
    design_requirements: {
      theme: formData.design_theme.trim() || '待确认',
      responsive: formData.responsive === '需要',
    },
    technical_constraints: {
      auth: formData.auth.trim() || '待确认',
      database: formData.database.trim() || '待确认',
      frontend: formData.frontend.trim() || '待确认',
      backend: formData.backend.trim() || '待确认',
      deployment: formData.deployment.trim() || '待确认',
      llm_usage: formData.llm_usage.trim() || '待确认',
    },
    non_functional_requirements: {
      security: parseList(formData.security_requirements),
      performance: parseList(formData.performance_requirements),
      usability: parseList(formData.usability_requirements),
    },
    in_scope: parseList(formData.in_scope),
    out_of_scope: parseList(formData.out_of_scope),
  };
}

function joinLines(items?: string[]): string {
  return (items || []).join('\n');
}

function summaryToFormData(summary: RequirementsSummary): StructuredFormData {
  return {
    product_name: summary.product_name || '',
    product_goal: summary.product_goal || '',
    target_users: joinLines(summary.target_users),
    platform: summary.platform || '网页应用（Web App）',
    mvp_features: (summary.mvp_features || [])
      .map((item) => [item.name || '待确认', item.description || '待确认', item.user_value || '待确认'].join('｜'))
      .join('\n'),
    v2_features: joinLines(summary.v2_features),
    ui_pages: (summary.ui_pages || [])
      .map((item) => [
        item.name || '待确认',
        (item.modules || []).join(','),
        item.notes || '',
      ].filter((part, index) => index < 2 || part).join('｜'))
      .join('\n'),
    interaction_notes: joinLines(summary.interaction_notes),
    design_theme: summary.design_requirements?.theme || '',
    responsive: summary.design_requirements?.responsive === false ? '不需要' : '需要',
    auth: summary.technical_constraints?.auth || '待确认',
    database: summary.technical_constraints?.database || '待确认',
    frontend: summary.technical_constraints?.frontend || '',
    backend: summary.technical_constraints?.backend || '',
    deployment: summary.technical_constraints?.deployment || '',
    llm_usage: summary.technical_constraints?.llm_usage || '',
    security_requirements: joinLines(summary.non_functional_requirements?.security),
    performance_requirements: joinLines(summary.non_functional_requirements?.performance),
    usability_requirements: joinLines(summary.non_functional_requirements?.usability),
    in_scope: joinLines(summary.in_scope),
    out_of_scope: joinLines(summary.out_of_scope),
  };
}

function normalizeDiffValue(value: unknown): string {
  if (value === undefined || value === null) return '未设置';
  if (typeof value === 'string') return value || '未设置';
  return JSON.stringify(value, null, 2);
}

function collectSummaryDiff(before: unknown, after: unknown, path = ''): SummaryDiffItem[] {
  if (JSON.stringify(before) === JSON.stringify(after)) {
    return [];
  }

  const beforeIsObject = typeof before === 'object' && before !== null && !Array.isArray(before);
  const afterIsObject = typeof after === 'object' && after !== null && !Array.isArray(after);

  if (beforeIsObject && afterIsObject) {
    const keys = Array.from(new Set([
      ...Object.keys(before as Record<string, unknown>),
      ...Object.keys(after as Record<string, unknown>),
    ])).sort();

    return keys.flatMap((key) =>
      collectSummaryDiff(
        (before as Record<string, unknown>)[key],
        (after as Record<string, unknown>)[key],
        path ? `${path}.${key}` : key
      )
    );
  }

  let changeType: SummaryDiffItem['changeType'] = 'modified';
  if (before === undefined || before === null || before === '') {
    changeType = 'added';
  } else if (after === undefined || after === null || after === '') {
    changeType = 'removed';
  }

  return [{
    path: path || 'root',
    changeType,
    before: normalizeDiffValue(before),
    after: normalizeDiffValue(after),
  }];
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return `${fallback}：${error.message}`;
  }
  return fallback;
}

const RAG_SOURCE_LABELS: Record<string, string> = {
  'team-api-guidelines.md': '团队接口规范',
  'history-copywriting-api.md': '历史接口示例（朋友圈文案助手）',
  'history-task-api.md': '历史接口示例（任务管理）',
};

function formatRagSourceLabel(source: string): string {
  const filename = source.split(/[/\\]/).pop() || source;
  return RAG_SOURCE_LABELS[filename] || filename.replace(/\.(md|txt)$/i, '').replace(/[-_]/g, ' ');
}

function getStageIndex(viewState: V2ViewState, entryMode: EntryMode): number {
  if (viewState === 'form') {
    return entryMode === 'structured' ? 0 : entryMode === 'prd' ? 2 : 4;
  }
  if (viewState === 'chatting') return 1;
  if (viewState === 'generating-prd' || viewState === 'review-prd') return 2;
  if (viewState === 'generating-api-docs' || viewState === 'review-api-docs') return 3;
  return 4;
}

function saveV2Session(data: V2SessionData) {
  try {
    localStorage.setItem(V2_SESSION_KEY, JSON.stringify(data));
  } catch {}
}

function loadV2Session(): V2SessionData | null {
  try {
    const raw = localStorage.getItem(V2_SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as V2SessionData;
    if (session.viewState?.startsWith('generating-')) {
      const fallback: Record<string, V2ViewState> = {
        'generating-prd': session.prdContent ? 'review-prd' : 'form',
        'generating-api-docs': session.apiDocsContent ? 'review-api-docs' : 'review-prd',
        'generating-prompts': session.promptsContent ? 'review-prompts' : session.apiDocsContent ? 'review-api-docs' : 'review-prd',
      };
      session.viewState = fallback[session.viewState] ?? 'form';
    }
    return session;
  } catch {
    return null;
  }
}

function buildConversationSeed(summary: RequirementsSummary): string {
  const features = summary.mvp_features.map((item) => `- ${item.name}：${item.description}`).join('\n');
  const pages = (summary.ui_pages || []).map((item) => `- ${item.name}${item.modules?.length ? `：${item.modules.join('、')}` : ''}`).join('\n');
  return [
    `我已经整理了一版结构化需求，请你像资深产品经理一样帮我补齐不清晰的问题。`,
    ``,
    `产品名称：${summary.product_name}`,
    `核心目标：${summary.product_goal}`,
    `目标用户：${summary.target_users.join('、') || '待确认'}`,
    `平台：${summary.platform}`,
    ``,
    `MVP 功能：`,
    features || '- 待确认',
    ``,
    `页面结构：`,
    pages || '- 待确认',
    ``,
    `请先指出最需要澄清的 3 个问题，再逐步和我确认。`,
  ].join('\n');
}

function validateStructuredForm(formData: StructuredFormData): StructuredFormErrors {
  const errors: StructuredFormErrors = {};

  if (!formData.product_name.trim()) errors.product_name = '请填写产品名称';
  if (!formData.product_goal.trim()) errors.product_goal = '请填写核心目标';
  if (parseList(formData.target_users).length === 0) errors.target_users = '请至少填写一个目标用户';
  if (!formData.platform.trim()) errors.platform = '请选择平台';

  const features = parseList(formData.mvp_features);
  if (features.length === 0) {
    errors.mvp_features = '请至少填写一个 MVP 功能';
  } else {
    const invalidFeature = features.find((line) => {
      const parts = line.split(/[|｜]/).map((part) => part.trim());
      return parts.length < 2 || !parts[0] || !parts[1];
    });
    if (invalidFeature) {
      errors.mvp_features = '请按“功能名称｜功能描述｜用户价值（可选）”逐行填写，且前两项不能为空';
    }
  }

  const pages = parseList(formData.ui_pages);
  if (pages.length > 0) {
    const invalidPage = pages.find((line) => {
      const parts = line.split(/[|｜]/).map((part) => part.trim());
      return parts.length < 2 || !parts[0] || !parts[1];
    });
    if (invalidPage) {
      errors.ui_pages = '请按“页面名｜模块1,模块2｜备注（可选）”逐行填写，至少提供页面名和模块列表';
    }
  }

  const overlaps = parseList(formData.in_scope).filter((item) => parseList(formData.out_of_scope).includes(item));
  if (overlaps.length > 0) {
    errors.in_scope = '在范围内与不在范围内不能出现相同条目';
    errors.out_of_scope = '在范围内与不在范围内不能出现相同条目';
  }

  return errors;
}

function isExampleFormData(data: StructuredFormData): boolean {
  return (Object.keys(EXAMPLE_FORM) as (keyof StructuredFormData)[]).every((key) => data[key] === EXAMPLE_FORM[key]);
}

function FormCollapsibleSection({
  title,
  description,
  defaultOpen = true,
  children,
}: {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 hover:bg-slate-50/80 [&::-webkit-details-marker]:hidden">
        <div>
          <div className="text-sm font-semibold text-slate-900">{title}</div>
          {description && <div className="mt-0.5 text-xs text-slate-500">{description}</div>}
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-5 border-t border-slate-100 px-5 py-5">{children}</div>
    </details>
  );
}

function FieldLabel({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="space-y-1">
      <div className="text-sm font-medium text-gray-800">{title}</div>
      {hint && <div className="text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <div className="mt-1 text-xs text-red-600">{message}</div>;
}

function TextInput(props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <input {...rest} className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`} />;
}

function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <textarea {...rest} className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 resize-none ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`} />;
}

function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <select {...rest} className={`w-full rounded-lg border px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`} />;
}

export default function AppV2() {
  const [viewState, setViewState] = useState<V2ViewState>('form');
  const [entryMode, setEntryMode] = useState<EntryMode>('structured');
  const [formData, setFormData] = useState<StructuredFormData>(DEFAULT_FORM);
  const [requirementsSummary, setRequirementsSummary] = useState<RequirementsSummary | null>(null);
  const [pendingSummary, setPendingSummary] = useState<RequirementsSummary | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState('');
  const [prdContent, setPrdContent] = useState('');
  const [apiDocsContent, setApiDocsContent] = useState('');
  const [promptsContent, setPromptsContent] = useState('');
  const [manualPrdInput, setManualPrdInput] = useState('');
  const [manualApiDocsInput, setManualApiDocsInput] = useState('');
  const [ragHits, setRagHits] = useState<RagHit[]>([]);
  const [pendingApiDocsPrd, setPendingApiDocsPrd] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isOptimizingDocument, setIsOptimizingDocument] = useState(false);
  const [isRetrievingRag, setIsRetrievingRag] = useState(false);
  const [isSyncingSummary, setIsSyncingSummary] = useState(false);
  const [error, setError] = useState('');
  const [formErrors, setFormErrors] = useState<StructuredFormErrors>({});
  const [showJsonPreview, setShowJsonPreview] = useState(false);
  const [prdGenerationStage, setPrdGenerationStage] = useState<PrdGenerationStage>('idle');
  const [prdReviewResult, setPrdReviewResult] = useState<PrdReviewResult | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const shouldStickToBottomRef = useRef(true);

  useEffect(() => {
    const session = loadV2Session();
    if (!session) return;
    if (session.viewState) setViewState(session.viewState);
    if (session.entryMode) setEntryMode(session.entryMode);
    if (session.formData) setFormData(session.formData);
    if (session.requirementsSummary !== undefined) setRequirementsSummary(session.requirementsSummary);
    if (session.pendingSummary !== undefined) setPendingSummary(session.pendingSummary);
    if (session.messages) setMessages(session.messages);
    if (session.conversationId) setConversationId(session.conversationId);
    if (session.prdContent) setPrdContent(session.prdContent);
    if (session.apiDocsContent) setApiDocsContent(session.apiDocsContent);
    if (session.promptsContent) setPromptsContent(session.promptsContent);
    if (session.manualPrdInput) setManualPrdInput(session.manualPrdInput);
    if (session.manualApiDocsInput) setManualApiDocsInput(session.manualApiDocsInput);
    if (session.ragHits) setRagHits(session.ragHits);
    if (session.pendingApiDocsPrd) setPendingApiDocsPrd(session.pendingApiDocsPrd);
    if (typeof session.showJsonPreview === 'boolean') setShowJsonPreview(session.showJsonPreview);
    if (session.prdReviewResult !== undefined) setPrdReviewResult(session.prdReviewResult);
  }, []);

  useEffect(() => {
    saveV2Session({
      viewState,
      entryMode,
      formData,
      requirementsSummary,
      pendingSummary,
      messages,
      conversationId,
      prdContent,
      apiDocsContent,
      promptsContent,
      manualPrdInput,
      manualApiDocsInput,
      ragHits,
      pendingApiDocsPrd,
      showJsonPreview,
      prdReviewResult,
    });
  }, [
    viewState,
    entryMode,
    formData,
    requirementsSummary,
    pendingSummary,
    messages,
    conversationId,
    prdContent,
    apiDocsContent,
    promptsContent,
    manualPrdInput,
    manualApiDocsInput,
    ragHits,
    pendingApiDocsPrd,
    showJsonPreview,
    prdReviewResult,
  ]);

  const requirementsPreview = useMemo(
    () => JSON.stringify(buildRequirementsSummary(formData), null, 2),
    [formData]
  );
  const currentStageIndex = useMemo(
    () => getStageIndex(viewState, entryMode),
    [viewState, entryMode]
  );
  const prdGenerationStatusText = useMemo(() => {
    if (prdGenerationStage === 'writing') return 'Writer Agent 正在起草...';
    if (prdGenerationStage === 'reviewing') return 'Review Agent 正在审查...';
    if (prdGenerationStage === 'rewriting') return 'Writer Agent 正在修订...';
    return '生成中...';
  }, [prdGenerationStage]);
  const summaryDiff = useMemo(
    () => (requirementsSummary && pendingSummary ? collectSummaryDiff(requirementsSummary, pendingSummary) : []),
    [requirementsSummary, pendingSummary]
  );
  const isExampleFilled = useMemo(() => isExampleFormData(formData), [formData]);
  const documentDownloadBasename = useMemo(
    () =>
      formData.product_name.trim() ||
      requirementsSummary?.product_name?.trim() ||
      'document',
    [formData.product_name, requirementsSummary?.product_name]
  );
  const stageItems = useMemo(
    () => [
      { index: 0, label: '结构化需求', enabled: entryMode === 'structured' || currentStageIndex >= 0, onClick: () => setViewState('form') },
      { index: 1, label: '澄清对话', enabled: messages.length > 0 || viewState === 'chatting', onClick: () => messages.length > 0 && setViewState('chatting') },
      { index: 2, label: 'PRD', enabled: !!prdContent || viewState === 'review-prd', onClick: () => prdContent && setViewState('review-prd') },
      { index: 3, label: '接口文档', enabled: !!apiDocsContent || viewState === 'review-api-docs', onClick: () => apiDocsContent && setViewState('review-api-docs') },
      { index: 4, label: '提示词', enabled: !!promptsContent || viewState === 'review-prompts' || entryMode === 'prompts', onClick: () => promptsContent && setViewState('review-prompts') },
    ],
    [entryMode, currentStageIndex, messages.length, viewState, prdContent, apiDocsContent, promptsContent]
  );

  const displayMessages = useMemo(() => {
    const visible = messages.filter((m) => m.role !== 'system').slice(1);
    if (streamingContent && viewState === 'chatting' && isStreaming) {
      return [...visible, { role: 'ai' as const, content: streamingContent }];
    }
    return visible;
  }, [messages, streamingContent, isStreaming, viewState]);

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
    if (viewState !== 'chatting') return;
    if (!shouldStickToBottomRef.current) return;
    const frame = requestAnimationFrame(() => {
      scrollChatToBottom(isStreaming);
    });
    return () => cancelAnimationFrame(frame);
  }, [displayMessages, streamingContent, isStreaming, viewState, scrollChatToBottom]);

  const updateField = (key: keyof StructuredFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    setFormErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const startStructuredConversation = async () => {
    const validationErrors = validateStructuredForm(formData);
    setFormErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      setError('请先修正表单中的格式问题，再开始澄清对话');
      return;
    }
    setError('');

    const summary = buildRequirementsSummary(formData);
    setRequirementsSummary(summary);
    setMessages([]);
    setStreamingContent('');
    setIsStreaming(true);
    shouldStickToBottomRef.current = true;
    setViewState('chatting');

    let accumulated = '';
    try {
      const result = await conversationApi.startConversationStream(
        buildConversationSeed(summary),
        {},
        CLARIFICATION_SYSTEM_PROMPT,
        (chunk) => {
          accumulated += chunk;
          setStreamingContent(accumulated);
        }
      );
      setMessages(result.messages);
      setConversationId(result.conversation_id);
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '启动澄清对话失败，请检查后端配置'));
      setViewState('form');
    } finally {
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  const continueConversation = async (userInput: string) => {
    if (isStreaming) return;
    shouldStickToBottomRef.current = true;
    const nextMessages: Message[] = [...messages, { role: 'human', content: userInput }];
    setMessages(nextMessages);
    setIsStreaming(true);
    setStreamingContent('');

    let accumulated = '';
    try {
      const result = await conversationApi.continueConversationStream(
        conversationId,
        messages,
        userInput,
        (chunk) => {
          accumulated += chunk;
          setStreamingContent(accumulated);
        }
      );
      setMessages(result.messages);
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '继续对话失败'));
      setMessages(messages);
    } finally {
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  const retrieveRagBeforeApiDocs = async (prd: string) => {
    if (!prd.trim()) {
      setError('缺少 PRD 内容，无法生成接口文档');
      return;
    }
    setError('');
    setRagHits([]);
    setPendingApiDocsPrd(prd);
    setIsRetrievingRag(true);
    try {
      const result = await conversationApi.retrieveApiDocsRag(prd, messages);
      setRagHits(result.hits || []);
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '检索接口规范与历史示例失败'));
      setPendingApiDocsPrd('');
    } finally {
      setIsRetrievingRag(false);
    }
  };

  const generateApiDocs = async (prd: string) => {
    if (!prd.trim()) {
      setError('缺少 PRD 内容，无法生成接口文档');
      return;
    }
    setError('');
    setRagHits([]);
    setPendingApiDocsPrd('');
    setApiDocsContent('');
    setStreamingContent('');
    setViewState('generating-api-docs');

    let accumulated = '';
    try {
      await conversationApi.generateApiDocsStream(prd, messages, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      setApiDocsContent(accumulated);
      setViewState('review-api-docs');
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '生成接口文档失败'));
      setViewState('review-prd');
    } finally {
      setStreamingContent('');
    }
  };

  const handleOptimizeDocument = async (
    docType: DocType,
    currentContent: string,
    instruction: string,
    context: string
  ) => {
    if (!currentContent.trim()) {
      setError('当前文档为空，无法优化');
      return;
    }
    setError('');
    setIsOptimizingDocument(true);
    setStreamingContent('');

    let accumulated = '';
    try {
      await conversationApi.optimizeDocumentStream(docType, currentContent, instruction, context, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      if (docType === 'prd') {
        setPrdContent(accumulated);
      } else if (docType === 'api-docs') {
        setApiDocsContent(accumulated);
      } else {
        setPromptsContent(accumulated);
      }
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '优化文档失败'));
    } finally {
      setStreamingContent('');
      setIsOptimizingDocument(false);
    }
  };

  const generatePrompts = async (prd: string, apiDocs: string) => {
    if (!prd.trim()) {
      setError('缺少 PRD 内容，无法生成提示词');
      return;
    }
    setError('');
    setPromptsContent('');
    setStreamingContent('');
    setViewState('generating-prompts');

    let accumulated = '';
    try {
      await conversationApi.generatePromptsStream(prd, apiDocs, (chunk) => {
        accumulated += chunk;
        setStreamingContent(accumulated);
      });
      setPromptsContent(accumulated);
      setViewState('review-prompts');
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '生成提示词失败'));
      setViewState(apiDocs.trim() ? 'review-api-docs' : 'review-prd');
    } finally {
      setStreamingContent('');
    }
  };

  const generatePrdForSummary = async (summary: RequirementsSummary) => {
    if (!summary) {
      setError('缺少结构化需求摘要，请先返回表单页重新开始');
      return;
    }
    setError('');
    setPrdContent('');
    setPrdReviewResult(null);
    setStreamingContent('');
    setViewState('generating-prd');
    setPrdGenerationStage('writing');

    let accumulated = '';
    try {
      const result = await conversationApi.generatePrdFromSummaryStream(
        summary,
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
      setViewState('review-prd');
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '生成 PRD 失败'));
      setPrdGenerationStage('error');
      setViewState('chatting');
    } finally {
      setStreamingContent('');
    }
  };

  const syncSummaryBackToForm = async () => {
    if (!requirementsSummary) {
      setError('缺少结构化需求摘要，请先从表单页开始');
      return;
    }
    if (messages.length === 0) {
      setError('当前没有可用于回填的澄清对话');
      return;
    }

    setError('');
    setIsSyncingSummary(true);
    try {
      const result = await conversationApi.syncSummaryFromConversation(requirementsSummary, messages);
      const updatedSummary = result.requirements_summary as unknown as RequirementsSummary;
      const diffs = collectSummaryDiff(requirementsSummary, updatedSummary);
      if (diffs.length === 0) {
        setRequirementsSummary(updatedSummary);
        setFormData(summaryToFormData(updatedSummary));
        setFormErrors({});
        await generatePrdForSummary(updatedSummary);
        return;
      }
      setPendingSummary(updatedSummary);
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, '回填结构化摘要失败'));
    } finally {
      setIsSyncingSummary(false);
    }
  };

  const resetPage = () => {
    setViewState('form');
    setFormData(DEFAULT_FORM);
    setRequirementsSummary(null);
    setPendingSummary(null);
    setMessages([]);
    setConversationId('');
    setPrdContent('');
    setPrdReviewResult(null);
    setApiDocsContent('');
    setPromptsContent('');
    setManualPrdInput('');
    setManualApiDocsInput('');
    setRagHits([]);
    setPendingApiDocsPrd('');
    setStreamingContent('');
    setIsStreaming(false);
    setIsRetrievingRag(false);
    setError('');
    setFormErrors({});
    localStorage.removeItem(V2_SESSION_KEY);
  };

  const goBackFromReviewPrd = () => {
    if (messages.length) {
      setViewState('chatting');
      return;
    }
    if (entryMode === 'prd' || entryMode === 'prompts') {
      setViewState('form');
      return;
    }
    setViewState('form');
  };

  const applyPendingSummary = () => {
    if (!pendingSummary) return;
    const nextSummary = pendingSummary;
    setRequirementsSummary(nextSummary);
    setFormData(summaryToFormData(nextSummary));
    setPendingSummary(null);
    setFormErrors({});
    void generatePrdForSummary(nextSummary);
  };

  const discardPendingSummary = () => {
    setPendingSummary(null);
  };

  const isDocumentStage =
    viewState === 'generating-prd' ||
    viewState === 'review-prd' ||
    viewState === 'generating-api-docs' ||
    viewState === 'review-api-docs' ||
    viewState === 'generating-prompts' ||
    viewState === 'review-prompts';
  const showApiDocsRagGate = isRetrievingRag || !!pendingApiDocsPrd;
  const showSummaryDiffGate =
    viewState === 'chatting' &&
    (isSyncingSummary || (!!pendingSummary && summaryDiff.length > 0));

  const cancelApiDocsRagGate = () => {
    setRagHits([]);
    setPendingApiDocsPrd('');
    setIsRetrievingRag(false);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <header className="z-20 flex-shrink-0 border-b border-slate-200 bg-white shadow-sm">
        <div className={`${V2_PAGE_CLASS} flex items-center justify-between gap-4 py-3`}>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">Vibe Coding v2</div>
              <div className="text-xs text-slate-500">结构化需求工作台</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={resetPage}
              title="清空本次任务的全部进度与内容"
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:border-red-300 hover:bg-red-100"
            >
              结束当前任务
            </button>
            <a href="/" className="text-sm text-slate-500 hover:text-slate-800">返回旧版</a>
          </div>
        </div>

        <div className="border-t border-slate-200 bg-slate-100/80">
          <div className={`${V2_PAGE_CLASS} flex flex-wrap items-center gap-x-3 gap-y-2 py-2.5`}>
            <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">流程进度</span>
            <div
              className="flex min-w-0 flex-1 flex-wrap items-center gap-1 rounded-lg border border-slate-200/80 bg-white p-1 shadow-sm"
              role="navigation"
              aria-label="流程进度"
            >
              {stageItems.map((stage) => {
                const isActive = currentStageIndex === stage.index;
                const isDone = currentStageIndex > stage.index;
                const canJump = stage.enabled;
                const disabledHint = !canJump && !isActive ? '完成前置步骤后可跳转' : undefined;
                return (
                  <button
                    key={stage.label}
                    type="button"
                    onClick={stage.onClick}
                    disabled={!canJump || isActive}
                    title={disabledHint ?? (isDone ? '点击查看该阶段' : undefined)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-sm'
                        : isDone
                        ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200/80 hover:bg-emerald-100'
                        : canJump
                        ? 'text-slate-700 hover:bg-slate-50'
                        : 'cursor-not-allowed text-slate-300'
                    }`}
                  >
                    {stage.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {error && (
        <div className={`${V2_PAGE_CLASS} mt-4 flex-shrink-0 rounded-xl border border-red-200 bg-red-50 py-3 text-sm text-red-700`}>
          {error}
        </div>
      )}

      {showSummaryDiffGate && (
        <div className={`${V2_PAGE_CLASS} flex min-h-0 flex-1 flex-col overflow-hidden`}>
          <SummaryDiffPanel
            items={summaryDiff}
            loading={isSyncingSummary}
            onConfirm={applyPendingSummary}
            onCancel={discardPendingSummary}
          />
        </div>
      )}

      {showApiDocsRagGate && (
        <div className={`${V2_PAGE_CLASS} flex min-h-0 flex-1 flex-col py-6`}>
          <div className="flex-shrink-0">
            <h2 className="text-lg font-semibold text-slate-900">生成接口文档前 · 确认参考资料</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
              系统会从<strong className="font-medium text-slate-800">团队接口规范</strong>和
              <strong className="font-medium text-slate-800">历史项目的接口文档</strong>
              里查找与当前 PRD 相关的内容，作为生成时的参考。确认后才会开始写接口文档。
            </p>
          </div>

          <div className="mt-5 min-h-0 flex-1 overflow-y-auto">
            {isRetrievingRag ? (
              <div className="flex h-full min-h-[12rem] items-center justify-center rounded-xl border border-slate-200 bg-white p-8">
                <div className="text-center">
                  <div className="text-sm font-medium text-slate-800">正在查找相关规范与示例…</div>
                  <p className="mt-2 text-sm text-slate-500">通常只需几秒钟</p>
                </div>
              </div>
            ) : ragHits.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-6">
                <div className="text-sm font-medium text-slate-800">未找到特别相关的团队资料</div>
                <p className="mt-2 text-sm text-slate-600">
                  将主要依据你当前的 PRD 生成接口文档，不会强行套用无关规范。
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-slate-600">
                  找到 {ragHits.length} 段可能相关的资料，生成时会优先参考这些内容：
                </p>
                {ragHits.map((hit, index) => (
                  <div
                    key={`${hit.source}-${hit.title}-${index}`}
                    className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex items-start gap-3">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-medium text-white">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-slate-900">{formatRagSourceLabel(hit.source)}</div>
                        <div className="mt-0.5 text-xs text-slate-500">章节：{hit.title}</div>
                        <p className="mt-2 text-sm leading-relaxed text-slate-700">{hit.content_preview}</p>
                        <details className="mt-3">
                          <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-800">
                            查看完整原文
                          </summary>
                          <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                            {hit.content}
                          </pre>
                        </details>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {!isRetrievingRag && (
            <div className="mt-6 flex flex-shrink-0 flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-5">
              <button
                type="button"
                onClick={cancelApiDocsRagGate}
                className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                返回 PRD
              </button>
              <button
                type="button"
                onClick={() => void generateApiDocs(pendingApiDocsPrd)}
                className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                开始生成接口文档
              </button>
            </div>
          )}
        </div>
      )}

      {viewState === 'form' && !showSummaryDiffGate && (
        <div className="min-h-0 flex-1 overflow-y-auto">
        <main className={`${V2_PAGE_CLASS} py-8`}>
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-slate-900">结构化需求录入</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">
              填写结构化表单后进入澄清对话；若已有 PRD 或提示词素材，也可从中间环节切入。
            </p>
            <div className="mt-5 w-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-2 text-xs font-medium text-slate-500">本次从哪里开始</div>
              <div
                className="flex w-full flex-wrap gap-1 rounded-xl border border-slate-200 bg-slate-100/80 p-1"
                role="tablist"
                aria-label="工作流起点"
              >
                {[
                  ['structured', '从零开始'],
                  ['prd', '从 PRD 开始'],
                  ['prompts', '从提示词开始'],
                ].map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    role="tab"
                    aria-selected={entryMode === mode}
                    onClick={() => {
                      setEntryMode(mode as EntryMode);
                      if (mode !== 'structured') setShowJsonPreview(false);
                    }}
                    className={`flex-1 rounded-lg px-4 py-2 text-center text-sm font-medium transition-colors sm:flex-none ${
                      entryMode === mode
                        ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {entryMode === 'structured' && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm text-slate-500">
                      可填充示例、清空内容，或预览结构化 JSON。
                    </p>
                    {isExampleFilled && (
                      <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                        当前为示例数据
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-1 gap-y-1">
                    <button
                      type="button"
                      onClick={() => {
                        setFormData(EXAMPLE_FORM);
                        setFormErrors({});
                        setError('');
                      }}
                      className="rounded-md px-2 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
                    >
                      填充示例
                    </button>
                    <span className="text-slate-300" aria-hidden>
                      ·
                    </span>
                    <button
                      type="button"
                      onClick={resetPage}
                      title="将清空整次任务的全部内容与进度"
                      className="rounded-md px-2 py-1 text-sm font-medium text-amber-800 hover:bg-amber-50"
                    >
                      清空全部
                    </button>
                    <span className="text-slate-300" aria-hidden>
                      ·
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowJsonPreview((prev) => !prev)}
                      className={`rounded-md px-2 py-1 text-sm font-medium ${
                        showJsonPreview ? 'bg-slate-800 text-white' : 'text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      {showJsonPreview ? '隐藏 JSON 预览' : '查看 JSON 预览'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {entryMode === 'structured' && showJsonPreview && (
            <div className="mb-8 rounded-2xl border border-slate-200 bg-slate-950 p-4">
              <div className="mb-2 text-sm font-medium text-slate-100">requirements_summary 预览</div>
              <div className="mb-3 text-xs text-slate-400">
                这里展示当前表单会转换成什么结构化 JSON，便于你检查 schema 映射是否符合预期。
              </div>
              <pre className="max-h-96 overflow-auto rounded-xl bg-slate-900 p-4 text-xs leading-6 text-slate-100">
                {requirementsPreview}
              </pre>
            </div>
          )}

          {entryMode === 'structured' && (
          <>
          <div className="w-full space-y-4">
            <FormCollapsibleSection title="产品与用户" description="名称、目标、用户与平台" defaultOpen>
              <div className="grid gap-5 lg:grid-cols-2">
                <div>
                  <FieldLabel title="产品名称" />
                  <TextInput invalid={!!formErrors.product_name} value={formData.product_name} onChange={(e) => updateField('product_name', e.target.value)} />
                  <FieldError message={formErrors.product_name} />
                </div>
                <div>
                  <FieldLabel title="平台" />
                  <SelectInput invalid={!!formErrors.platform} value={formData.platform} onChange={(e) => updateField('platform', e.target.value)}>
                    <option>网页应用（Web App）</option>
                    <option>微信小程序</option>
                    <option>App</option>
                    <option>命令行工具（CLI）</option>
                  </SelectInput>
                  <FieldError message={formErrors.platform} />
                </div>
              </div>
              <div>
                <FieldLabel title="核心目标" hint="一句话写清楚产品解决什么问题" />
                <TextArea invalid={!!formErrors.product_goal} rows={3} value={formData.product_goal} onChange={(e) => updateField('product_goal', e.target.value)} />
                <FieldError message={formErrors.product_goal} />
              </div>
              <div>
                <FieldLabel title="目标用户" hint="每行一个用户群体" />
                <TextArea invalid={!!formErrors.target_users} rows={4} placeholder={'微商\n销售\n自媒体从业者'} value={formData.target_users} onChange={(e) => updateField('target_users', e.target.value)} />
                <FieldError message={formErrors.target_users} />
              </div>
            </FormCollapsibleSection>

            <FormCollapsibleSection title="功能与页面" description="MVP、页面结构与关键交互" defaultOpen>
              <div>
                <FieldLabel title="MVP 功能" hint="每行一个功能，格式：功能名称｜功能描述｜用户价值（可选）" />
                <TextArea invalid={!!formErrors.mvp_features} rows={8} placeholder={'场景分类选择｜提供 7 个预设场景标签供用户单选｜降低用户思考成本\n一次生成 3 条文案｜基于当前条件返回 3 条不同文案｜提升可选性'} value={formData.mvp_features} onChange={(e) => updateField('mvp_features', e.target.value)} />
                <FieldError message={formErrors.mvp_features} />
              </div>
              <div>
                <FieldLabel title="未来规划（v2+）" hint="每行一个功能" />
                <TextArea rows={4} value={formData.v2_features} onChange={(e) => updateField('v2_features', e.target.value)} />
              </div>
              <div>
                <FieldLabel title="页面结构" hint="每行一个页面，格式：页面名｜模块1,模块2｜备注（可选）" />
                <TextArea invalid={!!formErrors.ui_pages} rows={5} placeholder={'输入页｜场景分类,场景描述,风格选择,生成按钮｜主输入视图\n结果页｜结果卡片,复制按钮,换一批按钮｜展示生成结果'} value={formData.ui_pages} onChange={(e) => updateField('ui_pages', e.target.value)} />
                <FieldError message={formErrors.ui_pages} />
              </div>
              <div>
                <FieldLabel title="关键交互" hint="每行一条关键流程或交互约束" />
                <TextArea rows={3} value={formData.interaction_notes} onChange={(e) => updateField('interaction_notes', e.target.value)} />
              </div>
            </FormCollapsibleSection>

            <FormCollapsibleSection title="设计与体验" description="视觉主题与响应式要求" defaultOpen={false}>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <FieldLabel title="视觉主题" />
                  <TextInput value={formData.design_theme} onChange={(e) => updateField('design_theme', e.target.value)} placeholder="例如：科技感暗色" />
                </div>
                <div>
                  <FieldLabel title="是否要求响应式" />
                  <SelectInput value={formData.responsive} onChange={(e) => updateField('responsive', e.target.value)}>
                    <option>需要</option>
                    <option>不需要</option>
                  </SelectInput>
                </div>
              </div>
            </FormCollapsibleSection>

            <FormCollapsibleSection title="技术约束" description="认证、存储、前后端与部署" defaultOpen={false}>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <FieldLabel title="用户认证" />
                  <SelectInput value={formData.auth} onChange={(e) => updateField('auth', e.target.value)}>
                    <option>待确认</option>
                    <option>需要登录</option>
                    <option>不需要登录</option>
                    <option>部分功能需要登录</option>
                  </SelectInput>
                </div>
                <div>
                  <FieldLabel title="数据存储" />
                  <SelectInput value={formData.database} onChange={(e) => updateField('database', e.target.value)}>
                    <option>待确认</option>
                    <option>需要数据库</option>
                    <option>不需要数据库</option>
                    <option>本地存储即可</option>
                  </SelectInput>
                </div>
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <div>
                  <FieldLabel title="前端技术约束" />
                  <TextInput value={formData.frontend} onChange={(e) => updateField('frontend', e.target.value)} placeholder="例如：React + TypeScript" />
                </div>
                <div>
                  <FieldLabel title="后端技术约束" />
                  <TextInput value={formData.backend} onChange={(e) => updateField('backend', e.target.value)} placeholder="例如：Serverless Function" />
                </div>
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <div>
                  <FieldLabel title="部署方式" />
                  <TextInput value={formData.deployment} onChange={(e) => updateField('deployment', e.target.value)} placeholder="例如：Vercel + Serverless" />
                </div>
                <div>
                  <FieldLabel title="LLM 使用说明" />
                  <TextArea rows={3} value={formData.llm_usage} onChange={(e) => updateField('llm_usage', e.target.value)} placeholder="例如：调用大模型一次生成 3 条朋友圈文案" />
                </div>
              </div>
            </FormCollapsibleSection>

            <FormCollapsibleSection title="非功能与范围" description="安全、性能、可用性与本期边界" defaultOpen={false}>
              <div className="grid gap-5 lg:grid-cols-3">
                <div>
                  <FieldLabel title="安全要求" hint="每行一条" />
                  <TextArea rows={4} value={formData.security_requirements} onChange={(e) => updateField('security_requirements', e.target.value)} />
                </div>
                <div>
                  <FieldLabel title="性能要求" hint="每行一条" />
                  <TextArea rows={4} value={formData.performance_requirements} onChange={(e) => updateField('performance_requirements', e.target.value)} />
                </div>
                <div>
                  <FieldLabel title="可用性要求" hint="每行一条" />
                  <TextArea rows={4} value={formData.usability_requirements} onChange={(e) => updateField('usability_requirements', e.target.value)} />
                </div>
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <div>
                  <FieldLabel title="在范围内" hint="每行一条" />
                  <TextArea invalid={!!formErrors.in_scope} rows={4} value={formData.in_scope} onChange={(e) => updateField('in_scope', e.target.value)} />
                  <FieldError message={formErrors.in_scope} />
                </div>
                <div>
                  <FieldLabel title="不在范围内（本期）" hint="每行一条" />
                  <TextArea invalid={!!formErrors.out_of_scope} rows={4} value={formData.out_of_scope} onChange={(e) => updateField('out_of_scope', e.target.value)} />
                  <FieldError message={formErrors.out_of_scope} />
                </div>
              </div>
            </FormCollapsibleSection>
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">填写完成后进入澄清对话，AI 将围绕结构化摘要补齐缺失信息。</p>
            <button
              type="button"
              onClick={startStructuredConversation}
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-800"
            >
              <MessageSquare className="h-4 w-4" />
              开始澄清对话
            </button>
          </div>
          </>
          )}

          {entryMode === 'prd' && (
            <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div>
                <FieldLabel title="PRD 内容" hint="粘贴现成 PRD 后，可以直接进入 PRD 阶段或继续生成接口文档/提示词" />
                <TextArea rows={20} value={manualPrdInput} onChange={(e) => setManualPrdInput(e.target.value)} placeholder="在这里粘贴完整 PRD..." />
              </div>
              <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
                <button
                  onClick={() => {
                    if (!manualPrdInput.trim()) {
                      setError('请先填写 PRD 内容');
                      return;
                    }
                    setError('');
                    setPrdContent(manualPrdInput);
                    setViewState('review-prd');
                  }}
                  className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  进入 PRD 环节
                </button>
                <button
                  onClick={() => {
                    setPrdContent(manualPrdInput);
                    void retrieveRagBeforeApiDocs(manualPrdInput);
                  }}
                  className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800"
                >
                  直接生成接口文档
                </button>
              </div>
            </div>
          )}

          {entryMode === 'prompts' && (
            <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div>
                <FieldLabel title="PRD 内容" hint="生成提示词时，PRD 为必填" />
                <TextArea rows={14} value={manualPrdInput} onChange={(e) => setManualPrdInput(e.target.value)} placeholder="在这里粘贴完整 PRD..." />
              </div>
              <div>
                <FieldLabel title="接口文档内容（可选）" hint="如果已有接口文档，提示词会更完整" />
                <TextArea rows={14} value={manualApiDocsInput} onChange={(e) => setManualApiDocsInput(e.target.value)} placeholder="可选：粘贴接口文档..." />
              </div>
              <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
                <button
                  onClick={() => {
                    if (!manualPrdInput.trim()) {
                      setError('请先填写 PRD 内容');
                      return;
                    }
                    setError('');
                    setPrdContent(manualPrdInput);
                    setApiDocsContent(manualApiDocsInput);
                    if (manualApiDocsInput.trim()) {
                      setViewState('review-api-docs');
                    } else {
                      setViewState('review-prd');
                    }
                  }}
                  className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  进入当前环节
                </button>
                <button
                  onClick={() => {
                    setPrdContent(manualPrdInput);
                    setApiDocsContent(manualApiDocsInput);
                    void generatePrompts(manualPrdInput, manualApiDocsInput);
                  }}
                  className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800"
                >
                  直接生成提示词
                </button>
              </div>
            </div>
          )}
        </main>
        </div>
      )}

      {viewState === 'chatting' && !showSummaryDiffGate && (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex-shrink-0 border-b border-slate-200 bg-white py-3">
            <div className={`${V2_PAGE_CLASS} flex flex-wrap items-center justify-between gap-3`}>
              <div className="min-w-0">
                <div className="text-sm font-medium text-slate-900">澄清对话</div>
                <div className="text-xs text-slate-500">AI 会围绕结构化摘要补齐不清晰项</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setViewState('form')}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
                >
                  返回表单
                </button>
                <button
                  type="button"
                  onClick={resetPage}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
                >
                  结束任务
                </button>
                <button
                  type="button"
                  onClick={syncSummaryBackToForm}
                  disabled={isStreaming || isSyncingSummary}
                  className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {isSyncingSummary ? '分析对话中…' : '生成 PRD'}
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
              <ChatInput onSend={continueConversation} loading={isStreaming} />
            </div>
          </div>
        </div>
      )}

      {isDocumentStage && !showApiDocsRagGate && (
        <div className="min-h-0 flex-1">
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

          {viewState === 'review-prd' && (
            <DocumentReview
              title="产品需求文档（PRD）"
              content={prdContent}
              downloadFilename={`${documentDownloadBasename}-PRD`}
              streamingContent={isOptimizingDocument ? streamingContent : undefined}
              isGenerating={isOptimizingDocument}
              reviewResult={prdReviewResult}
              actions={[
                {
                  label: messages.length ? '返回对话' : '返回入口',
                  variant: 'secondary',
                  onClick: goBackFromReviewPrd,
                  disabled: isOptimizingDocument,
                },
                {
                  label: '结束任务',
                  variant: 'ghost',
                  onClick: resetPage,
                  disabled: isOptimizingDocument,
                },
                {
                  label: '直接生成提示词',
                  variant: 'secondary',
                  onClick: () => void generatePrompts(prdContent, ''),
                  disabled: isOptimizingDocument,
                },
                {
                  label: '生成接口文档 →',
                  variant: 'primary',
                  onClick: () => void retrieveRagBeforeApiDocs(prdContent),
                  disabled: isOptimizingDocument,
                },
              ]}
              onSaveEdit={setPrdContent}
              onOptimize={(instruction) => void handleOptimizeDocument('prd', prdContent, instruction, '')}
            />
          )}

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

          {viewState === 'review-api-docs' && (
            <DocumentReview
              title="接口文档"
              content={apiDocsContent}
              downloadFilename={`${documentDownloadBasename}-API-Docs`}
              streamingContent={isOptimizingDocument ? streamingContent : undefined}
              isGenerating={isOptimizingDocument}
              actions={[
                {
                  label: '返回 PRD',
                  variant: 'secondary',
                  onClick: () => setViewState('review-prd'),
                  disabled: isOptimizingDocument,
                },
                {
                  label: '结束任务',
                  variant: 'ghost',
                  onClick: resetPage,
                  disabled: isOptimizingDocument,
                },
                {
                  label: '生成提示词 →',
                  variant: 'primary',
                  onClick: () => void generatePrompts(prdContent, apiDocsContent),
                  disabled: isOptimizingDocument,
                },
              ]}
              onSaveEdit={setApiDocsContent}
              onOptimize={(instruction) =>
                void handleOptimizeDocument('api-docs', apiDocsContent, instruction, prdContent)
              }
            />
          )}

          {viewState === 'generating-prompts' && (
            <DocumentReview
              title="提示词套件"
              content=""
              streamingContent={streamingContent}
              isGeneratingPhase={true}
              isGenerating={true}
              actions={[]}
              onSaveEdit={() => {}}
              onOptimize={() => {}}
            />
          )}

          {viewState === 'review-prompts' && (
            <DocumentReview
              title="提示词套件"
              content={promptsContent}
              downloadFilename={`${documentDownloadBasename}-Prompts`}
              streamingContent={isOptimizingDocument ? streamingContent : undefined}
              isGenerating={isOptimizingDocument}
              actions={[
                {
                  label: apiDocsContent.trim() ? '返回接口文档' : '返回 PRD',
                  variant: 'secondary',
                  onClick: () => setViewState(apiDocsContent.trim() ? 'review-api-docs' : 'review-prd'),
                  disabled: isOptimizingDocument,
                },
                {
                  label: '结束任务',
                  variant: 'ghost',
                  onClick: resetPage,
                  disabled: isOptimizingDocument,
                },
              ]}
              onSaveEdit={setPromptsContent}
              onOptimize={(instruction) =>
                void handleOptimizeDocument(
                  'prompts',
                  promptsContent,
                  instruction,
                  `${prdContent}\n\n${apiDocsContent}`
                )
              }
            />
          )}
        </div>
      )}
      </div>
    </div>
  );
}
