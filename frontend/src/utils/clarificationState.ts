import type { ClarificationMeta, Message } from '../types';
import type { ClarificationState, ClarificationStatus } from '../types/clarificationState';
import { getVisibleClarificationMessages } from './viewState';

function isAssistantRole(role: Message['role']): boolean {
  return role === 'assistant' || role === 'ai';
}

const NO_META_STATE: ClarificationState = {
  status: 'ready',
  openQuestions: [],
  warnings: [],
  statusLabel: null,
  needsConfirmBeforeGenerate: false,
};

function buildStatusLabel(openQuestions: string[], ready: boolean): string {
  if (openQuestions.length > 0) {
    return `澄清进行中 · ${openQuestions.length} 个待确认`;
  }
  if (ready) {
    return '澄清已收口 · 可生成 PRD';
  }
  return '澄清进行中';
}

function assessFromStructuredMeta(
  meta: ClarificationMeta,
  lastIsAi: boolean,
): ClarificationState {
  const openQuestions = meta.open_questions.filter((item) => item.trim()).slice(0, 5);
  const ready = meta.ready_to_generate && openQuestions.length === 0;

  let status: ClarificationStatus = 'ready';
  if (lastIsAi && openQuestions.length > 0) {
    status = 'awaiting_user_reply';
  } else if (lastIsAi && !ready) {
    status = 'collecting';
  }

  const needsConfirmBeforeGenerate = lastIsAi && openQuestions.length > 0;

  return {
    status,
    openQuestions: lastIsAi ? openQuestions : [],
    warnings: [],
    statusLabel: buildStatusLabel(openQuestions, ready),
    needsConfirmBeforeGenerate,
  };
}

export function assessClarificationState(
  messages: Message[],
  options?: {
    pendingClarificationMeta?: ClarificationMeta;
  },
): ClarificationState {
  const visible = getVisibleClarificationMessages(messages);
  if (visible.length === 0) {
    return NO_META_STATE;
  }

  const last = visible[visible.length - 1];
  const lastIsAi = isAssistantRole(last.role);
  const lastAi = [...visible].reverse().find((m) => isAssistantRole(m.role));

  if (options?.pendingClarificationMeta) {
    return assessFromStructuredMeta(options.pendingClarificationMeta, true);
  }

  if (lastAi?.clarification_meta && lastIsAi) {
    return assessFromStructuredMeta(lastAi.clarification_meta, true);
  }

  return NO_META_STATE;
}

export function clarificationStatusClass(state: ClarificationState): string {
  if (!state.needsConfirmBeforeGenerate && state.status === 'ready') {
    return 'text-emerald-700 bg-emerald-50';
  }
  return 'text-amber-700 bg-amber-50';
}
