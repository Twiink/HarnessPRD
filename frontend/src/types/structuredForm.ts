export type MvpFeatureRow = {
  name: string;
  description: string;
  user_value: string;
};

export type UiPageRow = {
  name: string;
  modules: string;
  notes: string;
};

export type StructuredFormData = {
  product_name: string;
  product_goal: string;
  target_users: string;
  platform: string;
  mvp_features: MvpFeatureRow[];
  v2_features: string;
  ui_pages: UiPageRow[];
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

export type StructuredFormErrors = Partial<Record<keyof StructuredFormData, string>> & {
  mvp_features?: string;
  ui_pages?: string;
};
