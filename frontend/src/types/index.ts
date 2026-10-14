export interface Message {
  role: 'system' | 'user' | 'human' | 'assistant' | 'ai';
  content: string;
  clarification_meta?: ClarificationMeta;
}

export interface ClarificationMeta {
  open_questions: string[];
  ready_to_generate: boolean;
}

export type ViewState =
  | 'form'
  | 'chatting'
  | 'generating-prd'
  | 'review-prd'
  | 'generating-api-docs'
  | 'review-api-docs'
  | 'generating-prompts'
  | 'review-prompts'
  | 'done';

export type DocType = 'prd' | 'api-docs' | 'prompts';

export interface DocAction {
  label: string;
  variant: 'primary' | 'secondary' | 'ghost' | 'link';
  onClick: () => void;
  disabled?: boolean;
}

export interface QuestionConfig {
  id: string;
  label: string;
  question: string;
  description: string;
  type: 'text' | 'textarea' | 'select' | 'radio';
  placeholder?: string;
  options?: string[];
  required: boolean;
  advanced: boolean;
}

export interface QuestionsConfig {
  base_questions: QuestionConfig[];
  advanced_questions: QuestionConfig[];
}

export interface ConversationResponse {
  conversation_id: string;
  messages: Message[];
  questions_config?: QuestionsConfig;
  response?: string;
  current_state: string;
  can_generate_prd?: boolean;
}

export interface PRDResponse {
  prd: string;
  status: string;
}

export interface ReviewIssue {
  severity: 'high' | 'medium' | 'low';
  section: string;
  problem: string;
  suggestion: string;
}

export interface PrdReviewResult {
  passed: boolean;
  summary: string;
  issues: ReviewIssue[];
}

export type PrdGenerationStage =
  | 'idle'
  | 'writing'
  | 'reviewing'
  | 'rewriting'
  | 'done'
  | 'error';

export interface GeneratePrdStreamResult {
  final_prd: string;
  review: PrdReviewResult | null;
  revision_applied: boolean;
}

export interface ConfigResponse {
  default_llm_provider: string;
  default_llm_model: string;
  anthropic_base_url: string;
  openai_base_url: string;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
}

export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
}

export type RunStepSummary = {
  step: string;
  input_tokens?: number;
  output_tokens?: number;
  duration_ms?: number;
};

export type InjectedSkillMeta = {
  skill_id: string;
  version: string;
  artifacts: string[];
};

export type RunSummary = {
  request_id: string;
  run_type: string;
  total_duration_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  llm_call_count: number;
  revision_applied?: boolean;
  steps?: RunStepSummary[];
  injected_skills?: InjectedSkillMeta[];
  budget?: {
    estimated_input_tokens: number;
    budget_tokens: number;
    ratio: number;
    level: string;
  };
};

export type ContextUsage = {
  estimated_input_tokens: number;
  budget_tokens: number;
  ratio: number;
  level: 'ok' | 'warn' | 'exceed';
};

/** 澄清阶段单轮 context 统计（前端按 SSE 累积） */
export type ClarificationRoundUsage = {
  round: number;
  label: string;
  usage: ContextUsage;
  durationMs?: number;
  outputTokens?: number;
};
