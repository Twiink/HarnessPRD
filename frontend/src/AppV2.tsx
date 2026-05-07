import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare, Sparkles } from 'lucide-react';
import MessageList from './components/MessageList';
import ChatInput from './components/ChatInput';
import DocumentReview from './components/DocumentReview';
import { conversationApi } from './services/api';
import type { Message, PrdGenerationStage, PrdReviewResult, RagHit } from './types';

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
type SummaryDiffItem = {
  path: string;
  changeType: 'added' | 'modified' | 'removed';
  before: string;
  after: string;
};

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
4. 在信息已经足够时，只需明确提示用户“如果没有更多补充，可以结束澄清”

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

function diffTypeLabel(changeType: SummaryDiffItem['changeType']): string {
  if (changeType === 'added') return '新增';
  if (changeType === 'removed') return '删除';
  return '修改';
}

function diffTypeClass(changeType: SummaryDiffItem['changeType']): string {
  if (changeType === 'added') return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  if (changeType === 'removed') return 'bg-rose-100 text-rose-700 border-rose-200';
  return 'bg-amber-100 text-amber-700 border-amber-200';
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return `${fallback}：${error.message}`;
  }
  return fallback;
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
  const [isRetrievingRag, setIsRetrievingRag] = useState(false);
  const [isSyncingSummary, setIsSyncingSummary] = useState(false);
  const [error, setError] = useState('');
  const [formErrors, setFormErrors] = useState<StructuredFormErrors>({});
  const [showJsonPreview, setShowJsonPreview] = useState(false);
  const [prdGenerationStage, setPrdGenerationStage] = useState<PrdGenerationStage>('idle');
  const [prdReviewResult, setPrdReviewResult] = useState<PrdReviewResult | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
      setError(result.hits?.length ? '已检索到接口规范与历史示例，请确认后生成接口文档。' : '未检索到 RAG 参考资料，确认后将仅基于 PRD 生成接口文档。');
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
      setError('已生成结构化摘要变更预览，请确认后生成 PRD。');
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
    setError('已取消本次回填预览。');
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">Vibe Coding v2</div>
              <div className="text-xs text-slate-500">结构化需求 {'->'} 对话补齐 {'->'} PRD</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={resetPage}
              className="text-sm text-slate-500 hover:text-slate-800"
            >
              结束当前任务
            </button>
            <a href="/" className="text-sm text-slate-500 hover:text-slate-800">返回旧版</a>
          </div>
        </div>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-6 pb-4">
          {stageItems.map((stage) => {
            const isActive = currentStageIndex === stage.index;
            const isDone = currentStageIndex > stage.index;
            const canJump = stage.enabled;
            return (
              <button
                key={stage.label}
                onClick={stage.onClick}
                disabled={!canJump || isActive}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-slate-900 text-white'
                    : isDone
                    ? 'bg-emerald-100 text-emerald-700'
                    : canJump
                    ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    : 'bg-slate-50 text-slate-300'
                }`}
              >
                {stage.label}
              </button>
            );
          })}
        </div>
      </header>

      {error && (
        <div className="mx-auto mt-4 max-w-5xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {pendingSummary && (
        <div className="mx-auto mt-4 max-w-5xl rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-amber-900">结构化摘要变更预览</div>
              <div className="mt-1 text-xs text-amber-800">
                以下是 AI 根据澄清对话建议更新的字段。这里只展示有差异的项，确认后会直接生成 PRD。
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={discardPendingSummary}
                className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-amber-900 hover:bg-amber-100"
              >
                取消
              </button>
              <button
                onClick={applyPendingSummary}
                className="rounded-lg bg-amber-900 px-3 py-2 text-xs font-medium text-white hover:bg-amber-800"
              >
                确认并生成 PRD
              </button>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            {summaryDiff.map((item) => (
              <div key={item.path} className="rounded-xl border border-amber-200 bg-white p-4">
                <div className="flex items-center gap-2">
                  <div className="text-xs font-medium text-amber-900">{item.path}</div>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${diffTypeClass(item.changeType)}`}>
                    {diffTypeLabel(item.changeType)}
                  </span>
                </div>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs text-slate-500">回填前</div>
                    <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-700">{item.before}</pre>
                  </div>
                  <div>
                    <div className="mb-1 text-xs text-slate-500">回填后</div>
                    <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">{item.after}</pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(isRetrievingRag || pendingApiDocsPrd) && (
        <div className="mx-auto mt-4 max-w-5xl rounded-2xl border border-sky-200 bg-sky-50 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-sky-950">
                {isRetrievingRag ? '正在检索接口规范与历史示例...' : 'RAG 命中结果'}
              </div>
              <div className="mt-1 text-xs text-sky-800">
                生成接口文档前，系统会先参考团队接口规范和历史接口文档示例。确认后才会进入正式生成。
              </div>
            </div>
            {!isRetrievingRag && (
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setRagHits([]);
                    setPendingApiDocsPrd('');
                    setError('已取消本次接口文档生成。');
                  }}
                  className="rounded-lg border border-sky-300 bg-white px-3 py-2 text-xs text-sky-900 hover:bg-sky-100"
                >
                  取消
                </button>
                <button
                  onClick={() => void generateApiDocs(pendingApiDocsPrd)}
                  className="rounded-lg bg-sky-900 px-3 py-2 text-xs font-medium text-white hover:bg-sky-800"
                >
                  确认使用这些参考资料生成
                </button>
              </div>
            )}
          </div>
          <div className="mt-4 space-y-3">
            {isRetrievingRag && (
              <div className="rounded-xl border border-sky-100 bg-white p-4 text-sm text-sky-800">
                正在从本地知识库检索 `团队接口规范`、`历史接口文档示例` 等相关片段...
              </div>
            )}
            {!isRetrievingRag && ragHits.length === 0 && (
              <div className="rounded-xl border border-sky-100 bg-white p-4 text-sm text-sky-800">
                没有命中可用参考资料。你仍然可以确认继续，系统会只基于当前 PRD 生成接口文档。
              </div>
            )}
            {!isRetrievingRag && ragHits.map((hit, index) => (
              <details key={`${hit.source}-${hit.title}-${index}`} className="rounded-xl border border-sky-100 bg-white p-4">
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-800">
                      RAG-{index + 1}
                    </span>
                    <span className="text-sm font-medium text-slate-900">{hit.source} / {hit.title}</span>
                    <span className="text-xs text-slate-400">score {hit.score}</span>
                  </div>
                  <div className="mt-2 text-xs leading-5 text-slate-600">{hit.content_preview}</div>
                </summary>
                <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                  {hit.content}
                </pre>
              </details>
            ))}
          </div>
        </div>
      )}

      {viewState === 'form' && (
        <div className="mx-auto max-w-5xl px-6 py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-slate-900">结构化需求录入</h1>
            <p className="mt-2 text-sm text-slate-500">
              这个页面既支持完整串联，也支持从 PRD 或提示词阶段直接开始。
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                ['structured', '结构化需求'],
                ['prd', '从 PRD 开始'],
                ['prompts', '从提示词开始'],
              ].map(([mode, label]) => (
                <button
                  key={mode}
                  onClick={() => setEntryMode(mode as EntryMode)}
                  className={`rounded-lg px-3 py-2 text-sm ${
                    entryMode === mode
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-4 flex gap-3">
              <button
                onClick={() => {
                  setFormData(EXAMPLE_FORM);
                  setEntryMode('structured');
                  setFormErrors({});
                  setError('');
                }}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                填充示例
              </button>
              <button
                onClick={resetPage}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
              >
                清空表单
              </button>
              <button
                onClick={() => setShowJsonPreview((prev) => !prev)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                {showJsonPreview ? '隐藏 JSON 预览' : '查看 JSON 预览'}
              </button>
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
          <div className="grid gap-8 lg:grid-cols-2">
            <div className="space-y-5">
              <div>
                <FieldLabel title="产品名称" />
                <TextInput invalid={!!formErrors.product_name} value={formData.product_name} onChange={(e) => updateField('product_name', e.target.value)} />
                <FieldError message={formErrors.product_name} />
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
              <div>
                <FieldLabel title="MVP 功能" hint="每行一个功能，格式：功能名称｜功能描述｜用户价值（可选）" />
                <TextArea invalid={!!formErrors.mvp_features} rows={8} placeholder={'场景分类选择｜提供 7 个预设场景标签供用户单选｜降低用户思考成本\n一次生成 3 条文案｜基于当前条件返回 3 条不同文案｜提升可选性'} value={formData.mvp_features} onChange={(e) => updateField('mvp_features', e.target.value)} />
                <FieldError message={formErrors.mvp_features} />
              </div>
              <div>
                <FieldLabel title="未来规划（v2+）" hint="每行一个功能" />
                <TextArea rows={5} value={formData.v2_features} onChange={(e) => updateField('v2_features', e.target.value)} />
              </div>
              <div>
                <FieldLabel title="页面结构" hint="每行一个页面，格式：页面名｜模块1,模块2｜备注（可选）" />
                <TextArea invalid={!!formErrors.ui_pages} rows={6} placeholder={'输入页｜场景分类,场景描述,风格选择,生成按钮｜主输入视图\n结果页｜结果卡片,复制按钮,换一批按钮｜展示生成结果'} value={formData.ui_pages} onChange={(e) => updateField('ui_pages', e.target.value)} />
                <FieldError message={formErrors.ui_pages} />
              </div>
              <div>
                <FieldLabel title="关键交互" hint="每行一条关键流程或交互约束" />
                <TextArea rows={4} value={formData.interaction_notes} onChange={(e) => updateField('interaction_notes', e.target.value)} />
              </div>
            </div>

            <div className="space-y-5">
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
              <div className="grid gap-4 sm:grid-cols-2">
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
              <div>
                <FieldLabel title="前端技术约束" />
                <TextInput value={formData.frontend} onChange={(e) => updateField('frontend', e.target.value)} placeholder="例如：React + TypeScript" />
              </div>
              <div>
                <FieldLabel title="后端技术约束" />
                <TextInput value={formData.backend} onChange={(e) => updateField('backend', e.target.value)} placeholder="例如：Serverless Function" />
              </div>
              <div>
                <FieldLabel title="部署方式" />
                <TextInput value={formData.deployment} onChange={(e) => updateField('deployment', e.target.value)} placeholder="例如：Vercel + Serverless" />
              </div>
              <div>
                <FieldLabel title="LLM 使用说明" />
                <TextArea rows={4} value={formData.llm_usage} onChange={(e) => updateField('llm_usage', e.target.value)} placeholder="例如：调用大模型一次生成 3 条朋友圈文案" />
              </div>
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
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={startStructuredConversation}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-800"
            >
              <MessageSquare className="h-4 w-4" />
              开始澄清对话
            </button>
          </div>
          </>
          )}

          {entryMode === 'prd' && (
            <div className="space-y-6">
              <div>
                <FieldLabel title="PRD 内容" hint="粘贴现成 PRD 后，可以直接进入 PRD 阶段或继续生成接口文档/提示词" />
                <TextArea rows={20} value={manualPrdInput} onChange={(e) => setManualPrdInput(e.target.value)} placeholder="在这里粘贴完整 PRD..." />
              </div>
              <div className="flex flex-wrap justify-end gap-3">
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
            <div className="space-y-6">
              <div>
                <FieldLabel title="PRD 内容" hint="生成提示词时，PRD 为必填" />
                <TextArea rows={14} value={manualPrdInput} onChange={(e) => setManualPrdInput(e.target.value)} placeholder="在这里粘贴完整 PRD..." />
              </div>
              <div>
                <FieldLabel title="接口文档内容（可选）" hint="如果已有接口文档，提示词会更完整" />
                <TextArea rows={14} value={manualApiDocsInput} onChange={(e) => setManualApiDocsInput(e.target.value)} placeholder="可选：粘贴接口文档..." />
              </div>
              <div className="flex flex-wrap justify-end gap-3">
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
        </div>
      )}

      {viewState === 'chatting' && (
        <div className="flex h-[calc(100vh-73px)] flex-col">
          <div className="border-b border-slate-200 bg-white px-6 py-3">
            <div className="mx-auto flex max-w-5xl items-center justify-between">
              <div>
                <div className="text-sm font-medium text-slate-900">澄清对话</div>
                <div className="text-xs text-slate-500">AI 会围绕结构化摘要补齐不清晰项</div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setViewState('form')} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50">
                  返回表单
                </button>
                <button onClick={resetPage} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50">
                  结束任务
                </button>
                <button
                  onClick={syncSummaryBackToForm}
                  disabled={isStreaming || isSyncingSummary}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  {isSyncingSummary ? '处理中...' : '结束澄清'}
                </button>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-4xl">
              <MessageList messages={displayMessages} loading={isStreaming && streamingContent === ''} />
              <div ref={messagesEndRef} />
            </div>
          </div>
          <div className="border-t border-slate-200 bg-white px-4 pb-4 pt-3">
            <div className="mx-auto max-w-4xl">
              <ChatInput onSend={continueConversation} loading={isStreaming} />
            </div>
          </div>
        </div>
      )}

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
          reviewResult={prdReviewResult}
          actions={[
            {
              label: messages.length ? '返回对话' : '返回入口',
              variant: 'secondary',
              onClick: goBackFromReviewPrd,
            },
            {
              label: '结束任务',
              variant: 'ghost',
              onClick: resetPage,
            },
            {
              label: '直接生成提示词',
              variant: 'secondary',
              onClick: () => void generatePrompts(prdContent, ''),
            },
            {
              label: '生成接口文档 →',
              variant: 'primary',
              onClick: () => void retrieveRagBeforeApiDocs(prdContent),
            },
          ]}
          onSaveEdit={setPrdContent}
          onOptimize={() => {}}
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
          actions={[
            {
              label: '返回 PRD',
              variant: 'secondary',
              onClick: () => setViewState('review-prd'),
            },
            {
              label: '结束任务',
              variant: 'ghost',
              onClick: resetPage,
            },
            {
              label: '生成提示词 →',
              variant: 'primary',
              onClick: () => void generatePrompts(prdContent, apiDocsContent),
            },
          ]}
          onSaveEdit={setApiDocsContent}
          onOptimize={() => {}}
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
          actions={[
            {
              label: apiDocsContent.trim() ? '返回接口文档' : '返回 PRD',
              variant: 'secondary',
              onClick: () => setViewState(apiDocsContent.trim() ? 'review-api-docs' : 'review-prd'),
            },
            {
              label: '结束任务',
              variant: 'ghost',
              onClick: resetPage,
            },
          ]}
          onSaveEdit={setPromptsContent}
          onOptimize={() => {}}
        />
      )}
    </div>
  );
}
