import type { Message } from '../types';
import type { ProjectSessionData } from '../services/sessionService';
import { buildRequirementsSummary, normalizeFormData } from './structuredFormTransform';

const BROWSER_DRAFT_KEY = 'vibecoding_session';

/** 从浏览器草稿恢复需求与文档；保存到方案后才清理来源。 */
export function loadBrowserDraft(): ProjectSessionData | null {
  try {
    const raw = localStorage.getItem(BROWSER_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Record<string, unknown>;
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    const source = (data.formData && typeof data.formData === 'object' ? data.formData : {}) as Record<string, unknown>;
    const text = (value: unknown) => typeof value === 'string' ? value : '';
    const formData = normalizeFormData({
      ...source,
      product_goal: source.product_goal || source.problem_solved || '',
      platform: source.platform || source.platform_type || '网页应用（Web App）',
      design_theme: source.design_theme || source.design_style || '',
      auth: source.auth || source.auth_required || '待确认',
      database: source.database || source.database_required || '待确认',
      frontend: source.frontend || source.tech_stack || '',
      interaction_notes: [
        text(source.interaction_notes),
        source.page_count ? `页面数量：${text(source.page_count)}` : '',
        source.third_party_apis ? `第三方服务：${text(source.third_party_apis)}` : '',
      ].filter(Boolean).join('\n'),
    });
    const prdContent = text(data.prdContent);
    const apiDocsContent = text(data.apiDocsContent);
    const promptsContent = text(data.promptsContent);
    const messages = Array.isArray(data.messages) ? data.messages as Message[] : [];
    const hasForm = Object.values(source).some((value) => typeof value === 'string' && value.trim());
    if (!hasForm && !prdContent && !apiDocsContent && !promptsContent && messages.length === 0) return null;
    return {
      viewState: promptsContent ? 'review-prompts' : apiDocsContent ? 'review-api-docs' : prdContent ? 'review-prd' : messages.length > 1 ? 'chatting' : 'form',
      entryMode: 'structured',
      formSubView: 'structured',
      formData,
      requirementsSummary: buildRequirementsSummary(formData),
      messages,
      conversationId: text(data.conversationId),
      prdContent,
      apiDocsContent,
      promptsContent,
    };
  } catch {
    return null;
  }
}

export function clearBrowserDraft(): void {
  try {
    localStorage.removeItem(BROWSER_DRAFT_KEY);
  } catch {
    // 浏览器禁用存储时，方案持久化仍由服务端负责。
  }
}
