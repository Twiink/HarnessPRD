import { FORM_TEMPLATES } from './formTemplates';

const TEMPLATE_TAG_STYLES: Record<string, { idle: string; active: string }> = {
  'friend-circle-copywriter': {
    idle: 'border-teal-200 bg-teal-50 text-teal-700 hover:border-teal-300 hover:bg-teal-100',
    active: 'border-teal-600 bg-teal-600 text-white shadow-sm ring-2 ring-teal-200',
  },
  'internal-approval': {
    idle: 'border-blue-200 bg-blue-50 text-blue-700 hover:border-blue-300 hover:bg-blue-100',
    active: 'border-blue-600 bg-blue-600 text-white shadow-sm ring-2 ring-blue-200',
  },
  'content-community': {
    idle: 'border-orange-200 bg-orange-50 text-orange-700 hover:border-orange-300 hover:bg-orange-100',
    active: 'border-orange-600 bg-orange-600 text-white shadow-sm ring-2 ring-orange-200',
  },
  'ai-copilot': {
    idle: 'border-violet-200 bg-violet-50 text-violet-700 hover:border-violet-300 hover:bg-violet-100',
    active: 'border-violet-600 bg-violet-600 text-white shadow-sm ring-2 ring-violet-200',
  },
};

type FormTemplatePickerProps = {
  selectedTemplateId: string | null;
  onSelectTemplate: (id: string) => void;
  onClear: () => void;
  hasFormContent: boolean;
};

export default function FormTemplatePicker({
  selectedTemplateId,
  onSelectTemplate,
  onClear,
  hasFormContent,
}: FormTemplatePickerProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-slate-500">行业模板</span>
      {FORM_TEMPLATES.map((template) => {
        const isSelected = template.id === selectedTemplateId;
        const styles = TEMPLATE_TAG_STYLES[template.id] ?? TEMPLATE_TAG_STYLES['friend-circle-copywriter'];
        return (
          <button
            key={template.id}
            type="button"
            onClick={() => onSelectTemplate(template.id)}
            title={template.description}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${isSelected ? styles.active : styles.idle}`}
          >
            {template.label}
          </button>
        );
      })}
      {hasFormContent && (
        <button
          type="button"
          onClick={onClear}
          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-500 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700"
        >
          清空数据
        </button>
      )}
    </div>
  );
}
