import type { Message, PrdReviewResult, RagHit } from '../types';

export type V2ViewState =
  | 'form'
  | 'chatting'
  | 'generating-prd'
  | 'review-prd'
  | 'generating-api-docs'
  | 'review-api-docs'
  | 'generating-prompts'
  | 'review-prompts';

export type EntryMode = 'structured' | 'prd' | 'prompts';

export type RequirementsSummary = {
  product_name: string;
  product_goal: string;
  target_users: string[];
  platform: string;
  mvp_features: Array<{
    name: string;
    description: string;
    user_value: string;
  }>;
  v2_features?: string[];
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

export type StructuredFormData = {
  product_name: string;
  product_goal: string;
  target_users: string;
  platform: string;
  mvp_features: string;
  v2_features: string;
  ui_pages: string;
  interaction_notes: string;
  design_theme: string;
  responsive: string;
  auth: string;
  database: string;
  frontend: string;
  backend: string;
  deployment: string;
  llm_usage: string;
  security_requirements: string;
  performance_requirements: string;
  usability_requirements: string;
  in_scope: string;
  out_of_scope: string;
};

export type V2SessionData = {
  viewState?: V2ViewState;
  entryMode?: EntryMode;
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
  ragHits?: RagHit[];
  pendingApiDocsPrd?: string;
  showJsonPreview?: boolean;
  prdReviewResult?: PrdReviewResult | null;
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
  session_data: V2SessionData;
};

export type SaveSessionResult = {
  id: string;
  title: string;
};

const API_BASE = '/api/session';

let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let pendingSave: { data: V2SessionData; id?: string } | null = null;

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

export async function saveSession(data: V2SessionData, id?: string): Promise<SaveSessionResult | null> {
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

export function debouncedSaveSession(data: V2SessionData, id?: string, delay = 1000): void {
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

/** 首次 save 后 replace 到 /v2/:id 时跳过 GET，避免 remount 覆盖本地 state */
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
