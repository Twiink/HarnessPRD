import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  consumeSkipNextSessionLoad,
  debouncedSaveSession,
  exportDeliveryPackage,
  flushPendingSave,
  loadSession,
  markSkipNextSessionLoad,
  saveSession,
  type EntryMode,
  type FormSubView,
  type RequirementsSummary,
  type ProjectSessionData,
  type WorkspaceViewState,
} from './services/sessionService';
import { buildArtifactNodes } from './utils/artifactProgress';
import {
  buildRequirementsSummary,
  DEFAULT_FORM,
  isSameFormData,
  summaryToFormData,
  validateStructuredForm,
} from './utils/structuredFormTransform';
import type { StructuredFormData, StructuredFormErrors } from './types/structuredForm';
import DocumentReviewWithHistory from './components/DocumentReviewWithHistory';
import SummaryDiffPanel from './components/SummaryDiffPanel';
import StreamErrorBanner from './components/StreamErrorBanner';
import FormEntryStage from './components/workspace/FormEntryStage';
import ClarificationStage from './components/workspace/ClarificationStage';
import AppHeader from './components/workspace/AppHeader';
import SessionLoadErrorPage, { SessionLoadingPage } from './components/workspace/SessionLoadErrorPage';
import { getTemplateById } from './components/structured-form/formTemplates';
import { PAGE_CLASS } from './constants/layout';
import { CLARIFICATION_SYSTEM_PROMPT } from './constants/clarificationPrompt';
import { buildConversationSeed } from './utils/clarificationSeed';
import { collectSummaryDiff } from './utils/summaryDiff';
import { applySessionData } from './utils/sessionHydration';
import { hasClarificationContent, isDocumentStage } from './utils/viewState';
import { assessClarificationState } from './utils/clarificationState';
import {
  parseClarificationMeta,
  stripClarificationStateBlock,
} from './utils/clarificationResponse';
import { canPerformAction, type DeliveryContext } from './utils/deliveryStage';
import { shortContentHash } from './utils/baseline';
import BaselineConfirmBanner, { countHighReviewIssuesForBaseline } from './components/BaselineConfirmBanner';
import { fetchVersionList } from './services/documentApi';
import { resolveCurrentVersionNo } from './utils/documentVersions';
import { conversationApi } from './services/api';
import { useGenerationObservability } from './hooks/useGenerationObservability';
import { useGenerationJob } from './hooks/useGenerationJob';
import { getErrorMessage } from './utils/streamErrors';
import { clearBrowserDraft, loadBrowserDraft } from './utils/browserDraft';
import type { DocType, DocAction, Message, PrdGenerationStage, PrdReviewResult } from './types';

type SessionLoadState = 'idle' | 'loading' | 'ready' | 'not_found' | 'error';

export default function App() {
  const navigate = useNavigate();
  const { id: routeId } = useParams<{ id: string }>();
  const [browserDraft] = useState(() => routeId ? null : loadBrowserDraft());
  const browserDraftApplied = useRef(false);
  const [sessionId, setSessionId] = useState<string | undefined>(routeId);
  const [isSavingSession, setIsSavingSession] = useState(false);
  const [sessionLoadState, setSessionLoadState] = useState<SessionLoadState>(routeId ? 'loading' : 'idle');
  const [viewState, setViewState] = useState<WorkspaceViewState>('form');
  const [entryMode, setEntryMode] = useState<EntryMode>('structured');
  const [formSubView, setFormSubView] = useState<FormSubView>('chooser');
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
  const [streamingContent, setStreamingContent] = useState('');
  const [clarificationStreamRaw, setClarificationStreamRaw] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSyncingSummary, setIsSyncingSummary] = useState(false);
  const [error, setError] = useState('');
  const [formErrors, setFormErrors] = useState<StructuredFormErrors>({});
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [prdGenerationStage, setPrdGenerationStage] = useState<PrdGenerationStage>('idle');
  const [prdReviewResult, setPrdReviewResult] = useState<PrdReviewResult | null>(null);
  const [prdBaselineConfirmed, setPrdBaselineConfirmed] = useState(false);
  const [prdBaselineConfirmedAt, setPrdBaselineConfirmedAt] = useState<string | null>(null);
  const [prdBaselineVersionId, setPrdBaselineVersionId] = useState<string | null>(null);
  const [prdBaselineVersionNo, setPrdBaselineVersionNo] = useState<number | null>(null);
  const [prdBaselineContentHash, setPrdBaselineContentHash] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null | undefined>(undefined);
  const prdGenerationStageRef = useRef<PrdGenerationStage>('idle');
  const obs = useGenerationObservability();

  const invalidateBaseline = useCallback(() => {
    setPrdBaselineConfirmed(false);
    setPrdBaselineConfirmedAt(null);
    setPrdBaselineVersionId(null);
    setPrdBaselineVersionNo(null);
    setPrdBaselineContentHash(null);
  }, []);

  const jobGen = useGenerationJob({
    sessionId,
    sessionLoadState,
    activeJobId,
    messages,
    obs,
    setContent: { setPrdContent, setApiDocsContent, setPromptsContent },
    setViewState,
    setPrdReviewResult,
    setStreamingContent,
    setError,
    setActiveJobId,
    setPrdGenerationStage,
    prdGenerationStageRef,
    onInvalidateBaseline: invalidateBaseline,
  });

  useEffect(() => {
    prdGenerationStageRef.current = prdGenerationStage;
  }, [prdGenerationStage]);

  const buildSessionSnapshot = useCallback((): ProjectSessionData => ({
    viewState,
    entryMode,
    formSubView,
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
    prdReviewResult,
    activeJobId,
    prdBaselineConfirmed,
    prdBaselineConfirmedAt,
    prdBaselineVersionId,
    prdBaselineVersionNo,
    prdBaselineContentHash,
  }), [
    viewState,
    entryMode,
    formSubView,
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
    prdReviewResult,
    activeJobId,
    prdBaselineConfirmed,
    prdBaselineConfirmedAt,
    prdBaselineVersionId,
    prdBaselineVersionNo,
    prdBaselineContentHash,
  ]);

  const applySessionSetters = useMemo(
    () => ({
      setViewState,
      setEntryMode,
      setFormSubView,
      setFormData,
      setRequirementsSummary,
      setPendingSummary,
      setMessages,
      setConversationId,
      setPrdContent,
      setApiDocsContent,
      setPromptsContent,
      setManualPrdInput,
      setManualApiDocsInput,
      setPrdReviewResult,
      setActiveJobId,
      setPrdBaselineConfirmed,
      setPrdBaselineConfirmedAt,
      setPrdBaselineVersionId,
      setPrdBaselineVersionNo,
      setPrdBaselineContentHash,
    }),
    [],
  );

  useEffect(() => {
    if (!routeId) {
      setSessionId(undefined);
      setSessionLoadState('idle');
      if (browserDraft && !browserDraftApplied.current) {
        applySessionData(browserDraft, applySessionSetters);
        browserDraftApplied.current = true;
      }
      return;
    }

    if (consumeSkipNextSessionLoad()) {
      setSessionId(routeId);
      setSessionLoadState('ready');
      return;
    }

    let cancelled = false;
    setSessionLoadState('loading');
    void loadSession(routeId).then((result) => {
      if (cancelled) return;
      if (result.status === 'ok') {
        applySessionData(result.data.session_data, applySessionSetters);
        setSessionId(routeId);
        setSessionLoadState('ready');
        return;
      }
      setSessionId(undefined);
      setSessionLoadState(result.status === 'not_found' ? 'not_found' : 'error');
    });

    return () => {
      cancelled = true;
    };
  }, [routeId, applySessionSetters, browserDraft]);

  useEffect(() => {
    if (!sessionId || sessionLoadState !== 'ready') return;
    debouncedSaveSession(buildSessionSnapshot(), sessionId);
  }, [sessionId, sessionLoadState, buildSessionSnapshot]);

  const ensureSessionCreated = useCallback(async (overrides?: Partial<ProjectSessionData>): Promise<string | null> => {
    const snapshot = { ...buildSessionSnapshot(), ...overrides };
    if (sessionId) {
      if (overrides && Object.keys(overrides).length > 0) {
        await saveSession(snapshot, sessionId);
      }
      return sessionId;
    }
    if (isSavingSession) return null;
    setIsSavingSession(true);
    const result = await saveSession(snapshot);
    setIsSavingSession(false);
    if (!result) {
      setError('保存方案失败，请稍后重试');
      return null;
    }
    markSkipNextSessionLoad();
    clearBrowserDraft();
    setSessionId(result.id);
    navigate(`/projects/${result.id}`, { replace: true });
    return result.id;
  }, [sessionId, isSavingSession, buildSessionSnapshot, navigate]);

  const goToSessionList = useCallback(async () => {
    await flushPendingSave();
    navigate('/projects');
  }, [navigate]);

  const summaryDiff = useMemo(
    () => (requirementsSummary && pendingSummary ? collectSummaryDiff(requirementsSummary, pendingSummary) : []),
    [requirementsSummary, pendingSummary],
  );
  const isTemplateFilled = useMemo(() => {
    if (!selectedTemplateId) return false;
    const template = getTemplateById(selectedTemplateId);
    return template ? isSameFormData(formData, template.data) : false;
  }, [formData, selectedTemplateId]);
  const hasFormContent = useMemo(() => !isSameFormData(formData, DEFAULT_FORM), [formData]);
  const documentDownloadBasename = useMemo(
    () =>
      formData.product_name.trim() ||
      requirementsSummary?.product_name?.trim() ||
      'document',
    [formData.product_name, requirementsSummary?.product_name],
  );
  const hasClarification = useMemo(() => hasClarificationContent(messages), [messages]);

  const clarificationState = useMemo(
    () =>
      assessClarificationState(messages, {
        pendingClarificationMeta:
          isStreaming && viewState === 'chatting'
            ? parseClarificationMeta(clarificationStreamRaw) ?? undefined
            : undefined,
      }),
    [messages, isStreaming, viewState, clarificationStreamRaw],
  );

  const buildDeliveryContext = useCallback(
    (summaryOverride?: RequirementsSummary | null): DeliveryContext => ({
      entryMode,
      requirementsSummary: summaryOverride ?? pendingSummary ?? requirementsSummary,
      messages,
      clarificationState,
      prdBaselineConfirmed,
      prdContent,
      apiDocsContent,
      promptsContent,
    }),
    [
      entryMode,
      requirementsSummary,
      pendingSummary,
      messages,
      clarificationState,
      prdBaselineConfirmed,
      prdContent,
      apiDocsContent,
      promptsContent,
    ],
  );

  const apiDocsGate = useMemo(
    () => canPerformAction(buildDeliveryContext(), 'generate_api_docs'),
    [buildDeliveryContext],
  );

  const promptsGate = useMemo(
    () => canPerformAction(buildDeliveryContext(), 'generate_prompts'),
    [buildDeliveryContext],
  );

  const exportGate = useMemo(
    () => canPerformAction(buildDeliveryContext(), 'export_bundle'),
    [buildDeliveryContext],
  );

  useEffect(() => {
    if (!prdBaselineConfirmed || !prdBaselineContentHash) return;
    let cancelled = false;
    void shortContentHash(prdContent).then((hash) => {
      if (cancelled) return;
      if (hash !== prdBaselineContentHash) {
        invalidateBaseline();
      }
    });
    return () => {
      cancelled = true;
    };
  }, [prdContent, prdBaselineConfirmed, prdBaselineContentHash, invalidateBaseline]);

  const handleConfirmBaseline = useCallback(async () => {
    if (!sessionId || !prdContent.trim()) return;
    const list = await fetchVersionList(sessionId, 'prd');
    const hash = await shortContentHash(prdContent);
    setPrdBaselineConfirmed(true);
    setPrdBaselineConfirmedAt(new Date().toISOString());
    setPrdBaselineVersionId(list.current_version_id);
    setPrdBaselineVersionNo(resolveCurrentVersionNo(list));
    setPrdBaselineContentHash(hash);
  }, [sessionId, prdContent]);

  const handleExportDelivery = useCallback(async () => {
    const gate = canPerformAction(buildDeliveryContext(), 'export_bundle');
    if (!gate.allowed) {
      setError(gate.reason ?? '无法导出');
      return;
    }
    const createdId = await ensureSessionCreated();
    if (!createdId) return;
    try {
      await exportDeliveryPackage(createdId);
    } catch (err) {
      setError(getErrorMessage(err, '导出交付包失败'));
    }
  }, [buildDeliveryContext, ensureSessionCreated]);

  const artifactHandlers = useMemo(
    () => ({
      onGoRequirements: () => {
        setFormSubView('structured');
        setViewState('form');
      },
      onGoClarification: () => {
        if (hasClarification) setViewState('chatting');
      },
      onGoPrd: () => {
        if (prdContent.trim()) setViewState('review-prd');
      },
      onGoApiDocs: () => {
        if (apiDocsContent.trim()) setViewState('review-api-docs');
      },
      onGoPrompts: () => {
        if (promptsContent.trim()) setViewState('review-prompts');
      },
    }),
    [hasClarification, prdContent, apiDocsContent, promptsContent],
  );

  const artifactNodes = useMemo(
    () =>
      buildArtifactNodes(
        {
          entryMode,
          viewState,
          formData,
          messages,
          prdContent,
          apiDocsContent,
          promptsContent,
          manualApiDocsInput,
        },
        artifactHandlers,
      ),
    [
      entryMode,
      viewState,
      formData,
      messages,
      prdContent,
      apiDocsContent,
      promptsContent,
      manualApiDocsInput,
      artifactHandlers,
    ],
  );

  const updateField = (key: keyof StructuredFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    setFormErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const handleSelectTemplate = (id: string) => {
    const template = getTemplateById(id);
    if (!template) return;
    setSelectedTemplateId(id);
    setFormData(JSON.parse(JSON.stringify(template.data)) as StructuredFormData);
    setFormErrors({});
    setError('');
  };

  const handleClearForm = () => {
    setFormData(JSON.parse(JSON.stringify(DEFAULT_FORM)) as StructuredFormData);
    setFormErrors({});
    setSelectedTemplateId(null);
    setError('');
  };

  const startStructuredConversation = async () => {
    const validationErrors = validateStructuredForm(formData);
    setFormErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      setError('请先修正表单中的格式问题，再开始澄清对话');
      return;
    }
    setError('');

    const createdId = await ensureSessionCreated();
    if (!createdId) return;

    const summary = buildRequirementsSummary(formData);
    setRequirementsSummary(summary);
    setMessages([]);
    obs.resetClarificationRounds();
    setClarificationStreamRaw('');
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
          setClarificationStreamRaw(accumulated);
          setStreamingContent(stripClarificationStateBlock(accumulated));
        },
        {
          ...obs.createClarificationHandlers(),
        },
      );
      setMessages(result.messages);
      setConversationId(result.conversation_id);
    } catch (err) {
      console.error(err);
      const { message } = obs.captureStreamError(err, { fallback: '启动澄清对话失败，请检查后端配置' });
      setError(message);
      setViewState('form');
    } finally {
      setClarificationStreamRaw('');
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  const continueConversation = async (userInput: string) => {
    if (isStreaming) return;
    obs.resetErrorMeta();
    const nextMessages: Message[] = [...messages, { role: 'human', content: userInput }];
    setMessages(nextMessages);
    setClarificationStreamRaw('');
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
          setClarificationStreamRaw(accumulated);
          setStreamingContent(stripClarificationStateBlock(accumulated));
        },
        {
          ...obs.createClarificationHandlers(),
        },
      );
      setMessages(result.messages);
    } catch (err) {
      console.error(err);
      const { message } = obs.captureStreamError(err, { fallback: '继续对话失败' });
      setError(message);
      setMessages(messages);
    } finally {
      setClarificationStreamRaw('');
      setStreamingContent('');
      setIsStreaming(false);
    }
  };

  const generateApiDocs = async (prd: string) => {
    if (!prd.trim()) {
      setError('缺少 PRD 内容，无法生成接口文档');
      return;
    }
    const gate = canPerformAction(buildDeliveryContext(), 'generate_api_docs');
    if (!gate.allowed) {
      setError(gate.reason ?? '无法生成接口文档');
      return;
    }
    const createdId = await ensureSessionCreated({ prdContent: prd });
    if (!createdId) return;

    await jobGen.startApiDocs(prd, createdId);
  };

  const handleOptimizeDocument = async (
    docType: DocType,
    currentContent: string,
    instruction: string,
    context: string,
  ) => {
    if (!currentContent.trim()) {
      setError('当前文档为空，无法优化');
      return;
    }
    const createdId = await ensureSessionCreated();
    if (!createdId) return;
    await jobGen.startOptimize(docType, currentContent, instruction, context);
  };

  const generatePrompts = async (prd: string, apiDocs: string) => {
    if (!prd.trim()) {
      setError('缺少 PRD 内容，无法生成提示词');
      return;
    }
    const gate = canPerformAction(buildDeliveryContext(), 'generate_prompts');
    if (!gate.allowed) {
      setError(gate.reason ?? '无法生成提示词');
      return;
    }
    const createdId = await ensureSessionCreated({
      prdContent: prd,
      apiDocsContent: apiDocs,
    });
    if (!createdId) return;

    await jobGen.startPrompts(prd, apiDocs, createdId);
  };

  const generatePrdForSummary = async (summary: RequirementsSummary) => {
    if (!summary) {
      setError('缺少结构化需求摘要，请先返回表单页重新开始');
      return;
    }
    const gate = canPerformAction(buildDeliveryContext(summary), 'generate_prd');
    if (!gate.allowed) {
      setError(gate.reason ?? '需求尚未就绪');
      return;
    }
    const createdId = await ensureSessionCreated();
    if (!createdId) return;

    await jobGen.startPrd(summary);
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

  const resetPage = async () => {
    await flushPendingSave();
    clearBrowserDraft();
    browserDraftApplied.current = true;
    setViewState('form');
    setEntryMode('structured');
    setFormSubView('chooser');
    setFormData(DEFAULT_FORM);
    setRequirementsSummary(null);
    setPendingSummary(null);
    setMessages([]);
    setConversationId('');
    setPrdContent('');
    setPrdReviewResult(null);
    invalidateBaseline();
    setApiDocsContent('');
    setPromptsContent('');
    setManualPrdInput('');
    setManualApiDocsInput('');
    setStreamingContent('');
    setIsStreaming(false);
    setError('');
    setFormErrors({});
    setSelectedTemplateId(null);
    setActiveJobId(undefined);
    obs.resetClarificationRounds();
    obs.resetGeneration();
    setSessionId(undefined);
    navigate('/');
  };

  const goBackFromReviewPrd = () => {
    if (messages.length) {
      setViewState('chatting');
      return;
    }
    if (entryMode === 'prd') {
      setFormSubView('import-prd');
      setViewState('form');
      return;
    }
    if (entryMode === 'prompts') {
      setFormSubView('import-prompts');
      setViewState('form');
      return;
    }
    setFormSubView('structured');
    setViewState('form');
  };

  const confirmSkipApiDocs = useCallback(() => {
    const gate = canPerformAction(buildDeliveryContext(), 'generate_prompts');
    if (!gate.allowed) {
      setError(gate.reason ?? '无法生成提示词');
      return;
    }
    if (!window.confirm('跳过接口文档时，提示词可能缺少 API 细节。是否继续？')) return;
    void generatePrompts(prdContent, '');
  }, [prdContent, buildDeliveryContext]);

  const prdReviewActions = useMemo((): DocAction[] => {
    const base: DocAction[] = [
      {
        label: messages.length ? '返回对话' : '返回入口',
        variant: 'secondary',
        onClick: goBackFromReviewPrd,
        disabled: jobGen.isOptimizingJob,
      },
    ];

    return [
      ...base,
      {
        label: '跳过接口文档，直接生成提示词',
        variant: 'link',
        onClick: confirmSkipApiDocs,
        disabled: jobGen.isOptimizingJob || !promptsGate.allowed,
      },
      {
        label: '生成接口文档',
        variant: 'primary',
        onClick: () => void generateApiDocs(prdContent),
        disabled: jobGen.isOptimizingJob || !apiDocsGate.allowed,
      },
    ];
  }, [
    messages.length,
    jobGen.isOptimizingJob,
    prdContent,
    apiDocsGate.allowed,
    promptsGate.allowed,
    goBackFromReviewPrd,
    confirmSkipApiDocs,
  ]);

  const applyPendingSummary = () => {
    if (!pendingSummary) return;
    const gate = canPerformAction(buildDeliveryContext(pendingSummary), 'generate_prd');
    if (!gate.allowed) {
      setError(gate.reason ?? '需求尚未就绪');
      return;
    }
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

  const showSummaryDiffGate =
    viewState === 'chatting' &&
    (isSyncingSummary || (!!pendingSummary && summaryDiff.length > 0));

  const enterPrdReviewFromInput = async () => {
    if (!manualPrdInput.trim()) {
      setError('请先填写 PRD 内容');
      return;
    }
    const createdId = await ensureSessionCreated({ prdContent: manualPrdInput });
    if (!createdId) return;
    setError('');
    setPrdContent(manualPrdInput);
    setViewState('review-prd');
  };

  const enterPromptsStageFromInput = async () => {
    if (!manualPrdInput.trim()) {
      setError('请先填写 PRD 内容');
      return;
    }
    const createdId = await ensureSessionCreated({
      prdContent: manualPrdInput,
      apiDocsContent: manualApiDocsInput,
    });
    if (!createdId) return;
    setError('');
    setPrdContent(manualPrdInput);
    setApiDocsContent(manualApiDocsInput);
    if (manualApiDocsInput.trim()) {
      setViewState('review-api-docs');
    } else {
      setViewState('review-prd');
    }
  };

  const startApiDocsFromPrdInput = async () => {
    setPrdContent(manualPrdInput);
    await generateApiDocs(manualPrdInput);
  };

  const startPromptsFromInput = async () => {
    setPrdContent(manualPrdInput);
    setApiDocsContent(manualApiDocsInput);
    await generatePrompts(manualPrdInput, manualApiDocsInput);
  };

  const actionLocked = isSavingSession;

  const structuredFormProps = useMemo(
    () => ({
      formData,
      formErrors,
      selectedTemplateId,
      isTemplateFilled,
      hasFormContent,
      actionLocked,
      onBack: () => setFormSubView('chooser'),
      onFieldChange: updateField,
      onFeaturesChange: (rows: StructuredFormData['features']) => {
        setFormData((prev) => ({ ...prev, features: rows }));
        setFormErrors((prev) => ({ ...prev, features: undefined }));
      },
      onUiPagesChange: (rows: StructuredFormData['ui_pages']) => {
        setFormData((prev) => ({ ...prev, ui_pages: rows }));
        setFormErrors((prev) => ({ ...prev, ui_pages: undefined }));
      },
      onSelectTemplate: handleSelectTemplate,
      onClearForm: handleClearForm,
      onStartClarification: () => void startStructuredConversation(),
    }),
    [
      formData,
      formErrors,
      selectedTemplateId,
      isTemplateFilled,
      hasFormContent,
      actionLocked,
    ],
  );

  if (routeId && sessionLoadState === 'loading') {
    return <SessionLoadingPage />;
  }

  if (routeId && sessionLoadState === 'not_found') {
    return (
      <SessionLoadErrorPage
        title="方案不存在"
        description="该方案可能已被删除，或链接无效。"
        onGoList={() => navigate('/projects')}
        onGoNew={() => navigate('/')}
      />
    );
  }

  if (routeId && sessionLoadState === 'error') {
    return (
      <SessionLoadErrorPage
        title="方案加载失败"
        description="暂时无法从服务端读取该方案，请稍后重试。"
        onGoList={() => navigate('/projects')}
        onGoNew={() => navigate('/')}
      />
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ground">
      <AppHeader
        artifactNodes={artifactNodes}
        projectName={formData.product_name.trim() || requirementsSummary?.product_name?.trim() || undefined}
        onGoSessionList={() => void goToSessionList()}
        onResetPage={() => void resetPage()}
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {error && (
          <StreamErrorBanner
            message={error}
            requestId={obs.errorRequestId}
            onCopyRequestId={() => void obs.copyErrorRequestId()}
            className={`${PAGE_CLASS} mt-4 flex-shrink-0`}
          />
        )}

        {showSummaryDiffGate && (
          <div className={`${PAGE_CLASS} flex min-h-0 flex-1 flex-col overflow-hidden`}>
            <SummaryDiffPanel
              items={summaryDiff}
              loading={isSyncingSummary}
              onConfirm={applyPendingSummary}
              onCancel={discardPendingSummary}
            />
          </div>
        )}

        {viewState === 'form' && !showSummaryDiffGate && (
          <FormEntryStage
            formSubView={formSubView}
            manualPrdInput={manualPrdInput}
            manualApiDocsInput={manualApiDocsInput}
            actionLocked={actionLocked}
            onSelectStructured={() => {
              setEntryMode('structured');
              setFormSubView('structured');
            }}
            onSelectImportPrd={() => {
              setEntryMode('prd');
              setFormSubView('import-prd');
            }}
            onSelectImportPrompts={() => {
              setEntryMode('prompts');
              setFormSubView('import-prompts');
            }}
            onManualPrdInputChange={setManualPrdInput}
            onManualApiDocsInputChange={setManualApiDocsInput}
            onEnterPrdReview={() => void enterPrdReviewFromInput()}
            onStartApiDocs={() => void startApiDocsFromPrdInput()}
            onEnterPromptsStage={() => void enterPromptsStageFromInput()}
            onStartPrompts={() => void startPromptsFromInput()}
            onBackToChooser={() => setFormSubView('chooser')}
            structuredFormProps={structuredFormProps}
          />
        )}

        {viewState === 'chatting' && !showSummaryDiffGate && (
          <ClarificationStage
            messages={messages}
            streamingContent={streamingContent}
            isStreaming={isStreaming}
            isSyncingSummary={isSyncingSummary}
            actionLocked={actionLocked}
            clarificationState={clarificationState}
            obs={obs}
            onBackToForm={() => {
              setFormSubView('structured');
              setViewState('form');
            }}
            onResetPage={() => void resetPage()}
            onSyncSummary={() => void syncSummaryBackToForm()}
            onSendMessage={continueConversation}
          />
        )}

        {isDocumentStage(viewState) && (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {viewState === 'generating-prd' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="prd"
                content={prdContent}
                onContentChange={setPrdContent}
                jobIdle={false}
                title="产品需求文档（PRD）"
                downloadFilename={`${documentDownloadBasename}-PRD`}
                streamingContent={streamingContent}
                isGeneratingPhase={true}
                isGenerating={true}
                generationSteps={obs.generationSteps}
                generationElapsed={obs.generationElapsed}
                generationHint={obs.generationHint}
                runSummary={obs.getRunSummary('prd')}
                reviewResult={prdReviewResult}
                actions={[]}
                onOptimize={() => {}}
              />
            )}

            {viewState === 'review-prd' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="prd"
                content={prdContent}
                onContentChange={setPrdContent}
                jobIdle={!jobGen.isOptimizingJob && !jobGen.isJobRunning}
                title="产品需求文档（PRD）"
                downloadFilename={`${documentDownloadBasename}-PRD`}
                streamingContent={jobGen.isOptimizingJob ? streamingContent : undefined}
                isGenerating={jobGen.isOptimizingJob}
                runSummary={obs.getRunSummary('prd')}
                reviewResult={prdReviewResult}
                headerBanner={({ revisionApplied, displayReview }) => (
                  <BaselineConfirmBanner
                    confirmed={prdBaselineConfirmed}
                    confirmedAt={prdBaselineConfirmedAt}
                    confirmedVersionNo={prdBaselineVersionNo}
                    revisionApplied={revisionApplied}
                    highIssueCount={countHighReviewIssuesForBaseline(displayReview, revisionApplied)}
                    onConfirm={() => void handleConfirmBaseline()}
                    confirmDisabled={!prdContent.trim() || jobGen.isOptimizingJob}
                  />
                )}
                actions={prdReviewActions}
                onOptimize={(instruction) => void handleOptimizeDocument('prd', prdContent, instruction, '')}
              />
            )}

            {viewState === 'generating-api-docs' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="api-docs"
                content={apiDocsContent}
                onContentChange={setApiDocsContent}
                jobIdle={false}
                title="接口文档"
                downloadFilename={`${documentDownloadBasename}-API-Docs`}
                streamingContent={streamingContent}
                isGeneratingPhase={true}
                isGenerating={true}
                generationSteps={obs.generationSteps}
                generationElapsed={obs.generationElapsed}
                generationHint={obs.generationHint}
                runSummary={obs.getRunSummary('api-docs')}
                actions={[]}
                onOptimize={() => {}}
              />
            )}

            {viewState === 'review-api-docs' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="api-docs"
                content={apiDocsContent}
                onContentChange={setApiDocsContent}
                jobIdle={!jobGen.isOptimizingJob && !jobGen.isJobRunning}
                title="接口文档"
                downloadFilename={`${documentDownloadBasename}-API-Docs`}
                streamingContent={jobGen.isOptimizingJob ? streamingContent : undefined}
                isGenerating={jobGen.isOptimizingJob}
                runSummary={obs.getRunSummary('api-docs')}
                onRegenerateStale={() => void generateApiDocs(prdContent)}
                actions={[
                  {
                    label: '返回 PRD',
                    variant: 'secondary',
                    onClick: () => setViewState('review-prd'),
                    disabled: jobGen.isOptimizingJob,
                  },
                  {
                    label: '生成提示词',
                    variant: 'primary',
                    onClick: () => void generatePrompts(prdContent, apiDocsContent),
                    disabled: jobGen.isOptimizingJob || !promptsGate.allowed,
                  },
                ]}
                onOptimize={(instruction) =>
                  void handleOptimizeDocument('api-docs', apiDocsContent, instruction, prdContent)
                }
              />
            )}

            {viewState === 'generating-prompts' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="prompts"
                content={promptsContent}
                onContentChange={setPromptsContent}
                jobIdle={false}
                title="提示词套件"
                downloadFilename={`${documentDownloadBasename}-Prompts`}
                streamingContent={streamingContent}
                isGeneratingPhase={true}
                isGenerating={true}
                generationSteps={obs.generationSteps}
                generationElapsed={obs.generationElapsed}
                generationHint={obs.generationHint}
                runSummary={obs.getRunSummary('prompts')}
                actions={[]}
                onOptimize={() => {}}
              />
            )}

            {viewState === 'review-prompts' && (
              <DocumentReviewWithHistory
                sessionId={sessionId}
                docType="prompts"
                content={promptsContent}
                onContentChange={setPromptsContent}
                jobIdle={!jobGen.isOptimizingJob && !jobGen.isJobRunning}
                title="提示词套件"
                downloadFilename={`${documentDownloadBasename}-Prompts`}
                streamingContent={jobGen.isOptimizingJob ? streamingContent : undefined}
                isGenerating={jobGen.isOptimizingJob}
                runSummary={obs.getRunSummary('prompts')}
                onRegenerateStale={() => void generatePrompts(prdContent, apiDocsContent)}
                actions={[
                  {
                    label: apiDocsContent.trim() ? '返回接口文档' : '返回 PRD',
                    variant: 'secondary',
                    onClick: () => setViewState(apiDocsContent.trim() ? 'review-api-docs' : 'review-prd'),
                    disabled: jobGen.isOptimizingJob,
                  },
                  {
                    label: '导出交付包',
                    variant: 'primary',
                    onClick: () => void handleExportDelivery(),
                    disabled: jobGen.isOptimizingJob || !exportGate.allowed,
                  },
                ]}
                onOptimize={(instruction) =>
                  void handleOptimizeDocument(
                    'prompts',
                    promptsContent,
                    instruction,
                    `${prdContent}\n\n${apiDocsContent}`,
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
