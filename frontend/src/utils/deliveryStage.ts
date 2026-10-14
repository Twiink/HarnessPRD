import type { EntryMode, RequirementsSummary } from '../services/sessionService';
import type { Message } from '../types';
import type { ReadinessResult } from '../types/readiness';
import type { ClarificationState } from '../types/clarificationState';

export type StageAction =
  | 'generate_prd'
  | 'generate_api_docs'
  | 'generate_prompts'
  | 'export_bundle';

export type DeliveryContext = {
  entryMode: EntryMode;
  requirementsSummary: RequirementsSummary | null;
  messages: Message[];
  readiness?: ReadinessResult;
  clarificationState?: ClarificationState;
  prdBaselineConfirmed?: boolean;
  prdContent?: string;
  apiDocsContent?: string;
  promptsContent?: string;
};

export type ActionGateResult = {
  allowed: boolean;
  reason?: string;
};

export function canPerformAction(ctx: DeliveryContext, action: StageAction): ActionGateResult {
  switch (action) {
    case 'generate_prd': {
      if (!ctx.requirementsSummary) {
        return { allowed: false, reason: '缺少结构化需求摘要' };
      }
      return { allowed: true };
    }
    case 'generate_api_docs': {
      if (!ctx.prdBaselineConfirmed) {
        return { allowed: false, reason: '请先确认需求基线' };
      }
      if (!ctx.prdContent?.trim()) {
        return { allowed: false, reason: 'PRD 内容为空' };
      }
      return { allowed: true };
    }
    case 'generate_prompts': {
      if (!ctx.prdBaselineConfirmed) {
        return { allowed: false, reason: '请先确认需求基线' };
      }
      if (!ctx.prdContent?.trim()) {
        return { allowed: false, reason: 'PRD 内容为空' };
      }
      return { allowed: true };
    }
    case 'export_bundle': {
      const hasContent = Boolean(
        ctx.prdContent?.trim() || ctx.apiDocsContent?.trim() || ctx.promptsContent?.trim(),
      );
      if (!hasContent) {
        return { allowed: false, reason: '没有可导出的文档内容' };
      }
      return { allowed: true };
    }
    default:
      return { allowed: true };
  }
}
