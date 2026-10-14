import type { Message, PrdReviewResult } from '../types';
import type { StructuredFormData } from '../types/structuredForm';
import {
  type EntryMode,
  type FormSubView,
  type RequirementsSummary,
  type ProjectSessionData,
  type WorkspaceViewState,
} from '../services/sessionService';
import { entryModeToFormSubView } from './formSubView';
import { normalizeFormData } from './structuredFormTransform';
import { repairStaleViewState } from './viewState';

export type SessionHydrationSetters = {
  setViewState: (v: WorkspaceViewState) => void;
  setEntryMode: (v: EntryMode) => void;
  setFormSubView: (v: FormSubView) => void;
  setFormData: (v: StructuredFormData) => void;
  setRequirementsSummary: (v: RequirementsSummary | null) => void;
  setPendingSummary: (v: RequirementsSummary | null) => void;
  setMessages: (v: Message[]) => void;
  setConversationId: (v: string) => void;
  setPrdContent: (v: string) => void;
  setApiDocsContent: (v: string) => void;
  setPromptsContent: (v: string) => void;
  setManualPrdInput: (v: string) => void;
  setManualApiDocsInput: (v: string) => void;
  setPrdReviewResult: (v: PrdReviewResult | null) => void;
  setActiveJobId: (v: string | null | undefined) => void;
  setPrdBaselineConfirmed: (v: boolean) => void;
  setPrdBaselineConfirmedAt: (v: string | null) => void;
  setPrdBaselineVersionId: (v: string | null) => void;
  setPrdBaselineVersionNo: (v: number | null) => void;
  setPrdBaselineContentHash: (v: string | null) => void;
};

export function applySessionData(session: ProjectSessionData, setters: SessionHydrationSetters): void {
  if (session.viewState) setters.setViewState(repairStaleViewState(session));
  if (session.entryMode) setters.setEntryMode(session.entryMode);
  if (session.formSubView) {
    setters.setFormSubView(session.formSubView);
  } else if (session.entryMode) {
    setters.setFormSubView(entryModeToFormSubView(session.entryMode));
  }
  if (session.formData) setters.setFormData(normalizeFormData(session.formData));
  if (session.requirementsSummary !== undefined) setters.setRequirementsSummary(session.requirementsSummary);
  if (session.pendingSummary !== undefined) setters.setPendingSummary(session.pendingSummary);
  if (session.messages) setters.setMessages(session.messages);
  if (session.conversationId) setters.setConversationId(session.conversationId);
  if (session.prdContent) setters.setPrdContent(session.prdContent);
  if (session.apiDocsContent) setters.setApiDocsContent(session.apiDocsContent);
  if (session.promptsContent) setters.setPromptsContent(session.promptsContent);
  if (session.manualPrdInput) setters.setManualPrdInput(session.manualPrdInput);
  if (session.manualApiDocsInput) setters.setManualApiDocsInput(session.manualApiDocsInput);
  if (session.prdReviewResult !== undefined) setters.setPrdReviewResult(session.prdReviewResult);
  if (session.activeJobId !== undefined) setters.setActiveJobId(session.activeJobId);
  if (session.prdBaselineConfirmed !== undefined) setters.setPrdBaselineConfirmed(session.prdBaselineConfirmed);
  if (session.prdBaselineConfirmedAt !== undefined) {
    setters.setPrdBaselineConfirmedAt(session.prdBaselineConfirmedAt);
  }
  if (session.prdBaselineVersionId !== undefined) {
    setters.setPrdBaselineVersionId(session.prdBaselineVersionId);
  }
  if (session.prdBaselineVersionNo !== undefined) {
    setters.setPrdBaselineVersionNo(session.prdBaselineVersionNo);
  }
  if (session.prdBaselineContentHash !== undefined) {
    setters.setPrdBaselineContentHash(session.prdBaselineContentHash);
  }
}
