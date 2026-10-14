export type ReadinessCheckItem = {
  id: string;
  label: string;
  passed: boolean;
  severity: 'blocker' | 'warning';
  detail?: string;
  fieldHint?: string;
};

export type ReadinessResult = {
  score: number;
  blockers: ReadinessCheckItem[];
  warnings: ReadinessCheckItem[];
  checks: ReadinessCheckItem[];
};
