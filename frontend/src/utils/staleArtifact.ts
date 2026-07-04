import type { DerivedFrom } from '../types/document';

export type StaleWarning = {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function buildStaleWarnings(params: {
  docType: 'api-docs' | 'prompts';
  derivedFrom?: DerivedFrom | null;
  prdCurrentVersionNo: number | null;
  apiDocsCurrentVersionNo?: number | null;
  onRegenerate?: () => void;
}): StaleWarning[] {
  const { derivedFrom, prdCurrentVersionNo, apiDocsCurrentVersionNo, docType, onRegenerate } = params;
  if (!derivedFrom) return [];

  const warnings: StaleWarning[] = [];

  if (
    prdCurrentVersionNo != null &&
    derivedFrom.prd_version_no != null &&
    derivedFrom.prd_version_no < prdCurrentVersionNo
  ) {
    const label = docType === 'api-docs' ? '接口文档' : '提示词';
    warnings.push({
      message: `PRD 已更新至 v${prdCurrentVersionNo}，当前${label}基于 v${derivedFrom.prd_version_no}。建议重新生成或手动核对。`,
      actionLabel: docType === 'api-docs' ? '重新生成接口文档' : '重新生成提示词',
      onAction: onRegenerate,
    });
  }

  if (
    docType === 'prompts' &&
    !derivedFrom.api_docs_skipped &&
    apiDocsCurrentVersionNo != null &&
    derivedFrom.api_docs_version_no != null &&
    derivedFrom.api_docs_version_no < apiDocsCurrentVersionNo
  ) {
    warnings.push({
      message: `接口文档已更新至 v${apiDocsCurrentVersionNo}，当前提示词基于 v${derivedFrom.api_docs_version_no}。建议重新生成或手动核对。`,
      actionLabel: '重新生成提示词',
      onAction: onRegenerate,
    });
  }

  return warnings;
}
