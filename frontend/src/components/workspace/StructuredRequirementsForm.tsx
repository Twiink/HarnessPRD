import { ArrowLeft, MessageSquare } from 'lucide-react';
import FeatureRowEditor from '../structured-form/FeatureRowEditor';
import UiPageRowEditor from '../structured-form/UiPageRowEditor';
import FormTemplatePicker from '../structured-form/FormTemplatePicker';
import { getTemplateById } from '../structured-form/formTemplates';
import {
  FieldError,
  FieldLabel,
  FormCollapsibleSection,
  SelectInput,
  TextArea,
  TextInput,
} from '../structured-form/formFields';
import type { StructuredFormData, StructuredFormErrors } from '../../types/structuredForm';
import type { FeatureRow, UiPageRow } from '../../types/structuredForm';

export type StructuredRequirementsFormProps = {
  formData: StructuredFormData;
  formErrors: StructuredFormErrors;
  selectedTemplateId: string | null;
  isTemplateFilled: boolean;
  hasFormContent: boolean;
  actionLocked: boolean;
  onBack: () => void;
  onFieldChange: (key: keyof StructuredFormData, value: string) => void;
  onFeaturesChange: (rows: FeatureRow[]) => void;
  onUiPagesChange: (rows: UiPageRow[]) => void;
  onSelectTemplate: (id: string) => void;
  onClearForm: () => void;
  onStartClarification: () => void;
};

export default function StructuredRequirementsForm({
  formData,
  formErrors,
  selectedTemplateId,
  isTemplateFilled,
  hasFormContent,
  actionLocked,
  onBack,
  onFieldChange,
  onFeaturesChange,
  onUiPagesChange,
  onSelectTemplate,
  onClearForm,
  onStartClarification,
}: StructuredRequirementsFormProps) {
  return (
    <div className="mx-auto max-w-5xl">
      <button
        type="button"
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        返回起点选择
      </button>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-ink">整理需求</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">
            先写下你已经确定的内容，不确定的可以留空，下一步的澄清对话会逐项追问。
          </p>
        </div>
      </div>
      <div className="mb-4">
        <FormTemplatePicker
          selectedTemplateId={selectedTemplateId}
          onSelectTemplate={onSelectTemplate}
          onClear={onClearForm}
          hasFormContent={hasFormContent}
        />
        {isTemplateFilled && selectedTemplateId && (
          <p className="mt-2 text-xs text-slate-500">
            当前内容来自示例「{getTemplateById(selectedTemplateId)?.label}」，可以直接修改。
          </p>
        )}
      </div>

      <div className="sheet">
        <FormCollapsibleSection index={1} title="产品与用户" description="名称、目标、用户与平台" defaultOpen>
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <FieldLabel title="产品名称" />
              <TextInput
                invalid={!!formErrors.product_name}
                value={formData.product_name}
                onChange={(e) => onFieldChange('product_name', e.target.value)}
              />
              <FieldError message={formErrors.product_name} />
            </div>
            <div>
              <FieldLabel title="平台" />
              <SelectInput
                invalid={!!formErrors.platform}
                value={formData.platform}
                onChange={(e) => onFieldChange('platform', e.target.value)}
              >
                <option>网页应用（Web App）</option>
                <option>微信小程序</option>
                <option>App</option>
                <option>命令行工具（CLI）</option>
              </SelectInput>
              <FieldError message={formErrors.platform} />
            </div>
          </div>
          <div>
            <FieldLabel title="核心目标" hint="一句话写清楚产品解决什么问题" />
            <TextArea
              invalid={!!formErrors.product_goal}
              rows={3}
              value={formData.product_goal}
              onChange={(e) => onFieldChange('product_goal', e.target.value)}
            />
            <FieldError message={formErrors.product_goal} />
          </div>
          <div>
            <FieldLabel title="目标用户" hint="每行一个用户群体" />
            <TextArea
              invalid={!!formErrors.target_users}
              rows={4}
              placeholder={'微商\n销售\n自媒体从业者'}
              value={formData.target_users}
              onChange={(e) => onFieldChange('target_users', e.target.value)}
            />
            <FieldError message={formErrors.target_users} />
          </div>
        </FormCollapsibleSection>

        <FormCollapsibleSection index={2} title="功能与页面" description="功能清单、页面结构与关键交互" defaultOpen>
          <div>
            <FieldLabel title="产品功能" hint="点击添加行，填写功能名称、描述与用户价值" />
            <FeatureRowEditor
              rows={formData.features}
              onChange={onFeaturesChange}
              error={formErrors.features}
            />
          </div>
          <div>
            <FieldLabel title="页面结构" hint="点击添加行，填写页面名称与主要模块" />
            <UiPageRowEditor
              rows={formData.ui_pages}
              onChange={onUiPagesChange}
              error={formErrors.ui_pages}
            />
          </div>
          <div>
            <FieldLabel title="关键交互" hint="每行一条关键流程或交互约束" />
            <TextArea
              rows={3}
              value={formData.interaction_notes}
              onChange={(e) => onFieldChange('interaction_notes', e.target.value)}
            />
          </div>
        </FormCollapsibleSection>

        <FormCollapsibleSection index={3} title="设计与体验" description="视觉主题与响应式要求" defaultOpen={false}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <FieldLabel title="视觉主题" />
              <TextInput
                value={formData.design_theme}
                onChange={(e) => onFieldChange('design_theme', e.target.value)}
                placeholder="例如：科技感暗色"
              />
            </div>
            <div>
              <FieldLabel title="是否要求响应式" />
              <SelectInput
                value={formData.responsive}
                onChange={(e) => onFieldChange('responsive', e.target.value)}
              >
                <option>需要</option>
                <option>不需要</option>
              </SelectInput>
            </div>
          </div>
        </FormCollapsibleSection>

        <FormCollapsibleSection index={4} title="技术约束" description="认证、存储、前后端与部署" defaultOpen={false}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <FieldLabel title="用户认证" />
              <SelectInput value={formData.auth} onChange={(e) => onFieldChange('auth', e.target.value)}>
                <option>待确认</option>
                <option>需要登录</option>
                <option>不需要登录</option>
                <option>部分功能需要登录</option>
              </SelectInput>
            </div>
            <div>
              <FieldLabel title="数据存储" />
              <SelectInput value={formData.database} onChange={(e) => onFieldChange('database', e.target.value)}>
                <option>待确认</option>
                <option>需要数据库</option>
                <option>不需要数据库</option>
                <option>本地存储即可</option>
              </SelectInput>
            </div>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <FieldLabel title="前端技术约束" />
              <TextInput
                value={formData.frontend}
                onChange={(e) => onFieldChange('frontend', e.target.value)}
                placeholder="例如：React + TypeScript"
              />
            </div>
            <div>
              <FieldLabel title="后端技术约束" />
              <TextInput
                value={formData.backend}
                onChange={(e) => onFieldChange('backend', e.target.value)}
                placeholder="例如：Serverless Function"
              />
            </div>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <FieldLabel title="部署方式" />
              <TextInput
                value={formData.deployment}
                onChange={(e) => onFieldChange('deployment', e.target.value)}
                placeholder="例如：Vercel + Serverless"
              />
            </div>
            <div>
              <FieldLabel title="LLM 使用说明" />
              <TextArea
                rows={3}
                value={formData.llm_usage}
                onChange={(e) => onFieldChange('llm_usage', e.target.value)}
                placeholder="例如：调用大模型一次生成 3 条朋友圈文案"
              />
            </div>
          </div>
        </FormCollapsibleSection>

        <FormCollapsibleSection index={5} title="非功能与范围" description="安全、性能、可用性与项目边界" defaultOpen={false}>
          <div className="grid gap-5 lg:grid-cols-3">
            <div>
              <FieldLabel title="安全要求" hint="每行一条" />
              <TextArea
                rows={4}
                value={formData.security_requirements}
                onChange={(e) => onFieldChange('security_requirements', e.target.value)}
              />
            </div>
            <div>
              <FieldLabel title="性能要求" hint="每行一条" />
              <TextArea
                rows={4}
                value={formData.performance_requirements}
                onChange={(e) => onFieldChange('performance_requirements', e.target.value)}
              />
            </div>
            <div>
              <FieldLabel title="可用性要求" hint="每行一条" />
              <TextArea
                rows={4}
                value={formData.usability_requirements}
                onChange={(e) => onFieldChange('usability_requirements', e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <div>
              <FieldLabel title="在范围内" hint="每行一条" />
              <TextArea
                invalid={!!formErrors.in_scope}
                rows={4}
                value={formData.in_scope}
                onChange={(e) => onFieldChange('in_scope', e.target.value)}
              />
              <FieldError message={formErrors.in_scope} />
            </div>
            <div>
              <FieldLabel title="不在范围内（项目）" hint="每行一条" />
              <TextArea
                invalid={!!formErrors.out_of_scope}
                rows={4}
                value={formData.out_of_scope}
                onChange={(e) => onFieldChange('out_of_scope', e.target.value)}
              />
              <FieldError message={formErrors.out_of_scope} />
            </div>
          </div>
        </FormCollapsibleSection>
      </div>

      <div className="sticky bottom-0 mt-6 flex flex-col gap-3 border-t-[1.5px] border-ink bg-ground/95 py-4 backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">下一步：AI 会根据这份需求追问缺失的信息。</p>
        <button
          type="button"
          onClick={onStartClarification}
          disabled={actionLocked}
          className="btn-primary px-5 py-2.5"
        >
          <MessageSquare className="h-4 w-4" aria-hidden />
          开始澄清对话
        </button>
      </div>
    </div>
  );
}
