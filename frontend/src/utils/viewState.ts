import type { Message } from '../types';
import type { ProjectSessionData, WorkspaceViewState } from '../services/sessionService';

export function getVisibleClarificationMessages(messages: Message[]): Message[] {
  return messages.filter((m) => m.role !== 'system').slice(1);
}

export function hasClarificationContent(messages: Message[]): boolean {
  return getVisibleClarificationMessages(messages).some((m) => m.content?.trim());
}

export function repairStaleViewState(session: ProjectSessionData): WorkspaceViewState {
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

export function isDocumentStage(viewState: WorkspaceViewState): boolean {
  return (
    viewState === 'generating-prd' ||
    viewState === 'review-prd' ||
    viewState === 'generating-api-docs' ||
    viewState === 'review-api-docs' ||
    viewState === 'generating-prompts' ||
    viewState === 'review-prompts'
  );
}
