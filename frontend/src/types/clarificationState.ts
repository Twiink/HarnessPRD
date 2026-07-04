export type ClarificationStatus = 'ready' | 'collecting' | 'awaiting_user_reply';

export type ClarificationState = {
  status: ClarificationStatus;
  openQuestions: string[];
  warnings: string[];
  /** 无 clarification_meta 时为 null，不展示状态标签 */
  statusLabel: string | null;
  needsConfirmBeforeGenerate: boolean;
};
