import type { Message } from '../types';
import type { V2SessionData, V2ViewState } from '../services/sessionService';

export function getVisibleClarificationMessages(messages: Message[]): Message[] {
  return messages.filter((m) => m.role !== 'system').slice(1);
}

export function hasClarificationContent(messages: Message[]): boolean {
  return getVisibleClarificationMessages(messages).some((m) => m.content?.trim());
}

export function repairStaleViewState(session: V2SessionData): V2ViewState {
  const viewState = session.viewState || 'form';
  const messages = session.messages || [];

  if (viewState === 'chatting' && !hasClarificationContent(messages)) {
    return 'form';
  }

  if (viewState !== 'form') {
    return viewState;
  }

  const hasPrd = Boolean(session.prdContent?.trim());
  const hasApiDocs = Boolean(session.apiDocsContent?.trim());
  const hasPrompts = Boolean(session.promptsContent?.trim());

  if (hasPrompts) return 'review-prompts';
  if (hasApiDocs) return 'review-api-docs';
  if (hasPrd) return 'review-prd';
  if (hasClarificationContent(messages) && session.entryMode === 'structured') return 'chatting';
  return 'form';
}

export function isDocumentStage(viewState: V2ViewState): boolean {
  return (
    viewState === 'generating-prd' ||
    viewState === 'review-prd' ||
    viewState === 'generating-api-docs' ||
    viewState === 'review-api-docs' ||
    viewState === 'generating-prompts' ||
    viewState === 'review-prompts'
  );
}
