export interface Message {
  role: 'system' | 'user' | 'human' | 'assistant' | 'ai';
  content: string;
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
  variant: 'primary' | 'secondary' | 'ghost';
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

export interface RagHit {
  source: string;
  title: string;
  score: number;
  content: string;
  content_preview: string;
}

export interface ConfigResponse {
  default_llm_provider: string;
  default_llm_model: string;
  anthropic_base_url: string;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
}

export interface LLMProvider {
  id: string;
  name: string;
  models: string[];
}
