import type { PrdReviewResult, RunSummary } from './index';
import type { QualityGateResult } from './qualityGate';

export type DocumentType = 'prd' | 'api-docs' | 'prompts';

export type DocumentSlotSummary = {
  doc_type: DocumentType;
  document_id: string | null;
  current_version_id: string | null;
  current_version_no: number | null;
  updated_at: string | null;
};

export type DocumentVersionSourceKind =
  | 'generate'
  | 'optimize'
  | 'auto_save'
  | 'checkpoint'
  | 'restore'
  | 'import';

export type DocumentVersionListItem = {
  id: string;
  version_no: number;
  source_kind: DocumentVersionSourceKind;
  created_at: string;
  content_preview: string;
  is_current: boolean;
  change_note?: string | null;
  restored_from_version_no?: number | null;
};

export type DerivedFrom = {
  prd_version_id?: string;
  prd_version_no?: number;
  api_docs_version_id?: string;
  api_docs_version_no?: number;
  api_docs_skipped?: boolean;
};

export type DocumentVersionDetail = {
  id: string;
  version_no: number;
  source_kind: string;
  content: string;
  source_job_id: string | null;
  parent_version_id: string | null;
  metadata: {
    run_summary?: RunSummary;
    review?: PrdReviewResult;
    quality_gate?: QualityGateResult;
    derived_from?: DerivedFrom;
    change_note?: string;
    restored_from_version_id?: string;
    restored_from_version_no?: number;
  };
  created_at: string;
  is_current: boolean;
};

export type VersionListResponse = {
  doc_type: DocumentType;
  document_id: string | null;
  current_version_id: string | null;
  current_version_no?: number | null;
  versions: DocumentVersionListItem[];
};

export type UpdateVersionNoteResponse = {
  version_id: string;
  version_no: number;
  change_note?: string | null;
};

export type CheckpointResponse = {
  version_id: string;
  version_no: number;
  document_id: string;
};

export type RestoreResponse = {
  version_id: string;
  version_no: number;
  document_id: string;
  content: string;
};
