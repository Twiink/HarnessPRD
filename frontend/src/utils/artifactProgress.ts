import type { Message } from '../types';
import type { EntryMode, WorkspaceViewState } from '../services/sessionService';
import type { StructuredFormData } from '../types/structuredForm';

export type ArtifactId =
  | 'requirements'
  | 'clarification'
  | 'prd'
  | 'api-docs'
  | 'prompts';

export type ArtifactStatus = 'pending' | 'active' | 'done';

export type ArtifactNode = {
  id: ArtifactId;
  label: string;
  status: ArtifactStatus;
  /** 该阶段内容是否已完成（与是否当前高亮无关） */
  completed: boolean;
  clickable: boolean;
  title?: string;
  onClick?: () => void;
};

export type ArtifactProgressInput = {
  entryMode: EntryMode;
  viewState: WorkspaceViewState;
  formData: StructuredFormData;
  messages: Message[];
  prdContent: string;
  apiDocsContent: string;
  promptsContent: string;
  manualApiDocsInput: string;
};

export type ArtifactProgressHandlers = {
  onGoRequirements: () => void;
  onGoClarification: () => void;
  onGoPrd: () => void;
  onGoApiDocs: () => void;
  onGoPrompts: () => void;
};

function hasClarificationContent(messages: Message[]): boolean {
  return messages
    .filter((m) => m.role !== 'system')
    .slice(1)
    .some((m) => m.content?.trim());
}

function getActiveArtifactId(entryMode: EntryMode, viewState: WorkspaceViewState): ArtifactId {
  if (viewState === 'chatting') return 'clarification';
  if (viewState === 'generating-prd' || viewState === 'review-prd') return 'prd';
  if (viewState === 'generating-api-docs' || viewState === 'review-api-docs') return 'api-docs';
  if (viewState === 'generating-prompts' || viewState === 'review-prompts') return 'prompts';
  if (viewState === 'form') {
    if (entryMode === 'structured') return 'requirements';
    return 'prd';
  }
  return 'prd';
}

function isRequirementsDone(input: ArtifactProgressInput): boolean {
  const hasName = Boolean(input.formData.product_name.trim());
  const hasProgress =
    hasClarificationContent(input.messages) ||
    Boolean(input.prdContent.trim());
  return hasName && hasProgress;
}

function buildNode(
  id: ArtifactId,
  label: string,
  done: boolean,
  activeId: ArtifactId,
  onClick: () => void,
): ArtifactNode {
  const isActive = id === activeId;
  const status: ArtifactStatus = isActive ? 'active' : done ? 'done' : 'pending';
  const clickable = done && !isActive;
  return {
    id,
    label,
    status,
    completed: done,
    clickable,
    title: isActive
      ? `当前阶段：${label}`
      : !done
        ? '尚未完成'
        : clickable
          ? `查看${label}`
          : undefined,
    onClick: clickable ? onClick : undefined,
  };
}

export function buildArtifactNodes(
  input: ArtifactProgressInput,
  handlers: ArtifactProgressHandlers,
): ArtifactNode[] {
  const activeId = getActiveArtifactId(input.entryMode, input.viewState);
  const prdDone = Boolean(input.prdContent.trim());
  const apiDone = Boolean(input.apiDocsContent.trim());
  const promptsDone = Boolean(input.promptsContent.trim());
  const clarificationDone = hasClarificationContent(input.messages);
  const requirementsDone = isRequirementsDone(input);

  if (input.entryMode === 'structured') {
    return [
      buildNode('requirements', '需求', requirementsDone, activeId, handlers.onGoRequirements),
      buildNode('clarification', '澄清', clarificationDone, activeId, handlers.onGoClarification),
      buildNode('prd', 'PRD', prdDone, activeId, handlers.onGoPrd),
      buildNode('api-docs', '接口文档', apiDone, activeId, handlers.onGoApiDocs),
      buildNode('prompts', '提示词', promptsDone, activeId, handlers.onGoPrompts),
    ];
  }

  if (input.entryMode === 'prd') {
    return [
      buildNode('prd', 'PRD', prdDone, activeId, handlers.onGoPrd),
      buildNode('api-docs', '接口文档', apiDone, activeId, handlers.onGoApiDocs),
      buildNode('prompts', '提示词', promptsDone, activeId, handlers.onGoPrompts),
    ];
  }

  const nodes: ArtifactNode[] = [
    buildNode('prd', 'PRD', prdDone || Boolean(input.formData.product_name.trim()), activeId, handlers.onGoPrd),
  ];
  if (apiDone || input.manualApiDocsInput.trim()) {
    nodes.push(buildNode('api-docs', '接口文档', apiDone, activeId, handlers.onGoApiDocs));
  }
  nodes.push(buildNode('prompts', '提示词', promptsDone, activeId, handlers.onGoPrompts));
  return nodes;
}
