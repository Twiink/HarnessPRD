import type { RequirementsSummary } from '../services/sessionService';
import type { MvpFeatureRow, StructuredFormData, StructuredFormErrors, UiPageRow } from '../types/structuredForm';

export const EMPTY_MVP_ROW: MvpFeatureRow = { name: '', description: '', user_value: '' };
export const EMPTY_UI_PAGE_ROW: UiPageRow = { name: '', modules: '', notes: '' };

export const DEFAULT_FORM: StructuredFormData = {
  product_name: '',
  product_goal: '',
  target_users: '',
  platform: '网页应用（Web App）',
  mvp_features: [{ ...EMPTY_MVP_ROW }],
  v2_features: '',
  ui_pages: [{ ...EMPTY_UI_PAGE_ROW }],
  interaction_notes: '',
  design_theme: '',
  responsive: '需要',
  auth: '待确认',
  database: '待确认',
  frontend: '',
  backend: '',
  deployment: '',
  llm_usage: '',
  security_requirements: '',
  performance_requirements: '',
  usability_requirements: '',
  in_scope: '',
  out_of_scope: '',
};

function parseList(raw: string): string[] {
  return raw
    .split('\n')
    .map((line) => line.trim().replace(/^[\d\-\*\.\、\s]+/, ''))
    .filter(Boolean);
}

function parseCommaList(raw: string): string[] {
  return raw
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function legacyParseMvpFeatures(raw: string): MvpFeatureRow[] {
  const rows = parseList(raw).map((line) => {
    const parts = line.split(/[|｜]/).map((part) => part.trim());
    return {
      name: parts[0] || '',
      description: parts[1] || parts[0] || '',
      user_value: parts[2] || '',
    };
  });
  return rows.length > 0 ? rows : [{ ...EMPTY_MVP_ROW }];
}

export function legacyParseUiPages(raw: string): UiPageRow[] {
  const rows = parseList(raw).map((line) => {
    const parts = line.split(/[|｜]/).map((part) => part.trim());
    return {
      name: parts[0] || '',
      modules: parts[1] || '',
      notes: parts[2] || '',
    };
  });
  return rows.length > 0 ? rows : [{ ...EMPTY_UI_PAGE_ROW }];
}

export function normalizeFormData(raw: unknown): StructuredFormData {
  const partial = (raw && typeof raw === 'object' ? raw : {}) as Partial<StructuredFormData> & {
    mvp_features?: unknown;
    ui_pages?: unknown;
  };
  const base: StructuredFormData = { ...DEFAULT_FORM, ...partial };

  if (typeof partial.mvp_features === 'string') {
    base.mvp_features = legacyParseMvpFeatures(partial.mvp_features);
  } else if (!Array.isArray(partial.mvp_features) || partial.mvp_features.length === 0) {
    base.mvp_features = [{ ...EMPTY_MVP_ROW }];
  }

  if (typeof partial.ui_pages === 'string') {
    base.ui_pages = legacyParseUiPages(partial.ui_pages);
  } else if (!Array.isArray(partial.ui_pages) || partial.ui_pages.length === 0) {
    base.ui_pages = [{ ...EMPTY_UI_PAGE_ROW }];
  }

  return base;
}

export function buildRequirementsSummary(formData: StructuredFormData): RequirementsSummary {
  return {
    product_name: formData.product_name.trim(),
    product_goal: formData.product_goal.trim(),
    target_users: parseList(formData.target_users),
    platform: formData.platform.trim(),
    mvp_features: formData.mvp_features
      .filter((row) => row.name.trim() || row.description.trim())
      .map((row) => ({
        name: row.name.trim() || '待确认',
        description: row.description.trim() || row.name.trim() || '待确认',
        user_value: row.user_value.trim() || '待确认',
      })),
    v2_features: parseList(formData.v2_features),
    ui_pages: formData.ui_pages
      .filter((row) => row.name.trim())
      .map((row) => ({
        name: row.name.trim(),
        modules: parseCommaList(row.modules),
        notes: row.notes.trim(),
      })),
    interaction_notes: parseList(formData.interaction_notes),
    design_requirements: {
      theme: formData.design_theme.trim() || '待确认',
      responsive: formData.responsive === '需要',
    },
    technical_constraints: {
      auth: formData.auth.trim() || '待确认',
      database: formData.database.trim() || '待确认',
      frontend: formData.frontend.trim() || '待确认',
      backend: formData.backend.trim() || '待确认',
      deployment: formData.deployment.trim() || '待确认',
      llm_usage: formData.llm_usage.trim() || '待确认',
    },
    non_functional_requirements: {
      security: parseList(formData.security_requirements),
      performance: parseList(formData.performance_requirements),
      usability: parseList(formData.usability_requirements),
    },
    in_scope: parseList(formData.in_scope),
    out_of_scope: parseList(formData.out_of_scope),
  };
}

function joinLines(items?: string[]): string {
  return (items || []).join('\n');
}

export function summaryToFormData(summary: RequirementsSummary): StructuredFormData {
  const mvpRows = (summary.mvp_features || []).map((item) => ({
    name: item.name || '',
    description: item.description || '',
    user_value: item.user_value || '',
  }));
  const pageRows = (summary.ui_pages || []).map((item) => ({
    name: item.name || '',
    modules: (item.modules || []).join('，'),
    notes: item.notes || '',
  }));

  return {
    product_name: summary.product_name || '',
    product_goal: summary.product_goal || '',
    target_users: joinLines(summary.target_users),
    platform: summary.platform || '网页应用（Web App）',
    mvp_features: mvpRows.length > 0 ? mvpRows : [{ ...EMPTY_MVP_ROW }],
    v2_features: joinLines(summary.v2_features),
    ui_pages: pageRows.length > 0 ? pageRows : [{ ...EMPTY_UI_PAGE_ROW }],
    interaction_notes: joinLines(summary.interaction_notes),
    design_theme: summary.design_requirements?.theme || '',
    responsive: summary.design_requirements?.responsive === false ? '不需要' : '需要',
    auth: summary.technical_constraints?.auth || '待确认',
    database: summary.technical_constraints?.database || '待确认',
    frontend: summary.technical_constraints?.frontend || '',
    backend: summary.technical_constraints?.backend || '',
    deployment: summary.technical_constraints?.deployment || '',
    llm_usage: summary.technical_constraints?.llm_usage || '',
    security_requirements: joinLines(summary.non_functional_requirements?.security),
    performance_requirements: joinLines(summary.non_functional_requirements?.performance),
    usability_requirements: joinLines(summary.non_functional_requirements?.usability),
    in_scope: joinLines(summary.in_scope),
    out_of_scope: joinLines(summary.out_of_scope),
  };
}

function nonEmptyMvpRows(rows: MvpFeatureRow[]): MvpFeatureRow[] {
  return rows.filter((row) => row.name.trim() || row.description.trim() || row.user_value.trim());
}

function nonEmptyPageRows(rows: UiPageRow[]): UiPageRow[] {
  return rows.filter((row) => row.name.trim() || row.modules.trim() || row.notes.trim());
}

export function validateStructuredForm(formData: StructuredFormData): StructuredFormErrors {
  const errors: StructuredFormErrors = {};

  if (!formData.product_name.trim()) errors.product_name = '请填写产品名称';
  if (!formData.product_goal.trim()) errors.product_goal = '请填写核心目标';
  if (parseList(formData.target_users).length === 0) errors.target_users = '请至少填写一个目标用户';
  if (!formData.platform.trim()) errors.platform = '请选择平台';

  const mvpRows = nonEmptyMvpRows(formData.mvp_features);
  if (mvpRows.length === 0) {
    errors.mvp_features = '请至少填写一个 MVP 功能';
  } else {
    const invalid = mvpRows.find((row) => !row.name.trim() || !row.description.trim());
    if (invalid) {
      errors.mvp_features = '每个 MVP 功能需填写名称和描述';
    }
  }

  const pageRows = nonEmptyPageRows(formData.ui_pages);
  if (pageRows.length === 0) {
    errors.ui_pages = '请至少填写一个页面';
  } else {
    const invalid = pageRows.find((row) => !row.name.trim());
    if (invalid) {
      errors.ui_pages = '每个页面需填写页面名称';
    }
  }

  const overlaps = parseList(formData.in_scope).filter((item) => parseList(formData.out_of_scope).includes(item));
  if (overlaps.length > 0) {
    errors.in_scope = '在范围内与不在范围内不能出现相同条目';
    errors.out_of_scope = '在范围内与不在范围内不能出现相同条目';
  }

  return errors;
}

export function isSameFormData(a: StructuredFormData, b: StructuredFormData): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
