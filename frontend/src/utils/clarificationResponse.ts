import type { ClarificationMeta } from '../types';

export const CLARIFICATION_STATE_FENCE = 'clarification_state';

const FENCE_BLOCK_RE = new RegExp(
  `\`\`\`${CLARIFICATION_STATE_FENCE}\\s*\\n([\\s\\S]*?)\\n\`\`\``,
  'i',
);

const FENCE_START_RE = new RegExp(`\\n?\`\`\`(?:${CLARIFICATION_STATE_FENCE})?\\s*$`, 'i');

function normalizeMeta(data: Record<string, unknown>): ClarificationMeta {
  const rawQuestions = data.open_questions;
  const openQuestions = Array.isArray(rawQuestions)
    ? rawQuestions
        .map((item) => String(item).trim())
        .filter(Boolean)
        .slice(0, 5)
    : [];

  let readyToGenerate = Boolean(data.ready_to_generate);
  if (openQuestions.length > 0) {
    readyToGenerate = false;
  }

  return {
    open_questions: openQuestions,
    ready_to_generate: readyToGenerate,
  };
}

function parseMetaJson(jsonText: string): ClarificationMeta | null {
  const trimmed = jsonText.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    return normalizeMeta(parsed as Record<string, unknown>);
  } catch {
    return null;
  }
}

/** 从完整或流式累积文本中解析 clarification_meta（仅当 JSON 块已完整时返回） */
export function parseClarificationMeta(text: string): ClarificationMeta | null {
  if (!text.trim()) return null;
  const match = text.match(FENCE_BLOCK_RE);
  if (!match?.[1]) return null;
  return parseMetaJson(match[1]);
}

/** 流式展示：实时剥离 clarification_state 代码块（含未闭合的部分块） */
export function stripClarificationStateBlock(text: string): string {
  if (!text) return text;

  const complete = text.match(FENCE_BLOCK_RE);
  if (complete?.index != null) {
    return text.slice(0, complete.index).replace(/\s+$/, '');
  }

  const marker = `\`\`\`${CLARIFICATION_STATE_FENCE}`;
  const markerIdx = text.indexOf(marker);
  if (markerIdx >= 0) {
    return text.slice(0, markerIdx).replace(/\s+$/, '');
  }

  for (let length = marker.length - 1; length >= 3; length -= 1) {
    const partial = marker.slice(0, length);
    if (text.endsWith(partial)) {
      return text.slice(0, -partial.length).replace(/\s+$/, '');
    }
  }

  const partialFence = text.match(FENCE_START_RE);
  if (partialFence?.index != null) {
    return text.slice(0, partialFence.index).replace(/\s+$/, '');
  }

  return text;
}
