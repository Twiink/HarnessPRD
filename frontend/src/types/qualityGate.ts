export type QualityGateCheck = {
  id: string;
  label: string;
  passed: boolean;
  severity: 'high' | 'medium' | 'low';
  detail?: string | null;
};

export type QualityGateResult = {
  passed: boolean;
  score: number;
  checked_at: string;
  doc_type: 'prd' | 'api-docs' | 'prompts';
  checks: QualityGateCheck[];
};
