export type SummaryDiffItem = {
  path: string;
  changeType: 'added' | 'removed' | 'modified';
  before: string;
  after: string;
};
