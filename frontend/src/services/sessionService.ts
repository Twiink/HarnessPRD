import type { Message, PrdReviewResult } from '../types';
import type { StructuredFormData } from '../types/structuredForm';

export type { StructuredFormData } from '../types/structuredForm';

export type WorkspaceViewState =
  | 'form'
  | 'chatting'
  | 'generating-prd'
  | 'review-prd'
  | 'generating-api-docs'
  | 'review-api-docs'
  | 'generating-prompts'
  | 'review-prompts';

export type EntryMode = 'structured' | 'prd' | 'prompts';

export type FormSubView = 'chooser' | 'structured' | 'import-prd' | 'import-prompts';

export type RequirementsSummary = {
  product_name: string;
  product_goal: string;
  target_users: string[];
  platform: string;
  features: Array<{
    name: string;
    description: string;
    user_value: string;
  }>;
  ui_pages?: Array<{
    name: string;
    modules?: string[];
    notes?: string;
  }>;
  interaction_notes?: string[];
  design_requirements?: {
    theme?: string;
    responsive?: boolean;
  };
  technical_constraints?: {
    auth?: string;
    database?: string;
    frontend?: string;
    backend?: string;
    deployment?: string;
    llm_usage?: string;
  };
  non_functional_requirements?: {
    security?: string[];
    performance?: string[];
    usability?: string[];
  };
  in_scope?: string[];
  out_of_scope?: string[];
};

export type ProjectSessionData = {
  viewState?: WorkspaceViewState;
  entryMode?: EntryMode;
  formSubView?: FormSubView;
  formData?: StructuredFormData;
  requirementsSummary?: RequirementsSummary | null;
  pendingSummary?: RequirementsSummary | null;
  messages?: Message[];
  conversationId?: string;
  prdContent?: string;
  apiDocsContent?: string;
  promptsContent?: string;
  manualPrdInput?: string;
  manualApiDocsInput?: string;
  prdReviewResult?: PrdReviewResult | null;
  activeJobId?: string | null;
  prdBaselineConfirmed?: boolean;
  prdBaselineConfirmedAt?: string | null;
  prdBaselineVersionId?: string | null;
  prdBaselineVersionNo?: number | null;
  prdBaselineContentHash?: string | null;
};

export type SessionSummary = {
  id: string;
  title: string;
  entry_mode?: string;
  current_stage?: string;
  status?: string;
  created_at: string;
  updated_at: string;
};

export type SessionDetail = SessionSummary & {
  session_data: ProjectSessionData;
};

export type SaveSessionResult = {
  id: string;
  title: string;
};

const API_BASE = '/api/session';

let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let pendingSave: { data: ProjectSessionData; id?: string } | null = null;

async function request<T>(url: string, options?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }));
      console.error('Session API error:', err.detail || response.statusText);
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error('Session API request failed:', error);
    return null;
  }
}

export async function listSessions(): Promise<SessionSummary[]> {
  const result = await request<{ items: SessionSummary[] }>(`${API_BASE}/list`);
  return result?.items ?? [];
}

export type LoadSessionResult =
  | { status: 'ok'; data: SessionDetail }
  | { status: 'not_found' }
  | { status: 'error' };

export async function loadSession(id: string): Promise<LoadSessionResult> {
  try {
    const response = await fetch(`${API_BASE}/${id}`);
    if (response.status === 404) {
      return { status: 'not_found' };
    }
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }));
      console.error('Session API error:', err.detail || response.statusText);
      return { status: 'error' };
    }
    const data = (await response.json()) as SessionDetail;
    return { status: 'ok', data };
  } catch (error) {
    console.error('Session API request failed:', error);
    return { status: 'error' };
  }
}

export async function saveSession(data: ProjectSessionData, id?: string): Promise<SaveSessionResult | null> {
  return request<SaveSessionResult>(`${API_BASE}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, session_data: data }),
  });
}

export async function deleteSession(id: string): Promise<boolean> {
  const result = await request<{ ok: boolean }>(`${API_BASE}/${id}`, { method: 'DELETE' });
  return result?.ok === true;
}

export function debouncedSaveSession(data: ProjectSessionData, id?: string, delay = 1000): void {
  if (!id) return;
  pendingSave = { data, id };
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const payload = pendingSave;
    pendingSave = null;
    debounceTimer = null;
    if (payload?.id) {
      void saveSession(payload.data, payload.id);
    }
  }, delay);
}

export async function exportDeliveryPackage(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${sessionId}/export-delivery`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: '导出失败' }));
    throw new Error(typeof err.detail === 'string' ? err.detail : '导出失败');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';
  const filename = parseContentDispositionFilename(disposition) || 'delivery.zip';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function parseContentDispositionFilename(disposition: string): string | null {
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      // fall through to filename=
    }
  }
  const match = disposition.match(/filename="([^"]+)"/);
  return match?.[1] ?? null;
}

export async function flushPendingSave(): Promise<void> {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  if (pendingSave?.id) {
    const payload = pendingSave;
    pendingSave = null;
    await saveSession(payload.data, payload.id);
  }
}

/** 首次 save 后 replace 到 /projects/:id 时跳过 GET，避免 remount 覆盖本地 state */
export let skipNextSessionLoad = false;

export function markSkipNextSessionLoad(): void {
  skipNextSessionLoad = true;
}

export function consumeSkipNextSessionLoad(): boolean {
  if (skipNextSessionLoad) {
    skipNextSessionLoad = false;
    return true;
  }
  return false;
}
