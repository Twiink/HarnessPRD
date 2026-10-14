import type { RequirementsSummary } from '../services/sessionService';

export function buildConversationSeed(summary: RequirementsSummary): string {
  const features = summary.mvp_features.map((item) => `- ${item.name}：${item.description}`).join('\n');
  const pages = (summary.ui_pages || [])
    .map((item) => `- ${item.name}${item.modules?.length ? `：${item.modules.join('、')}` : ''}`)
    .join('\n');
  return [
    '我已经整理了一版结构化需求，请你像资深产品经理一样帮我补齐不清晰的问题。',
    '',
    `产品名称：${summary.product_name}`,
    `核心目标：${summary.product_goal}`,
    `目标用户：${summary.target_users.join('、') || '待确认'}`,
    `平台：${summary.platform}`,
    '',
    'MVP 功能：',
    features || '- 待确认',
    '',
    '页面结构：',
    pages || '- 待确认',
    '',
    '请先指出最需要澄清的 3 个问题，再逐步和我确认。',
  ].join('\n');
}
