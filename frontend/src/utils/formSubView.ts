import type { EntryMode, FormSubView } from '../services/sessionService';

export function entryModeToFormSubView(entryMode: EntryMode): FormSubView {
  switch (entryMode) {
    case 'structured':
      return 'structured';
    case 'prd':
      return 'import-prd';
    case 'prompts':
      return 'import-prompts';
    default:
      return 'structured';
  }
}
