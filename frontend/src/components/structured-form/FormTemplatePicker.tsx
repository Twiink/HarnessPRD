import { FORM_TEMPLATES } from './formTemplates';

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
      <span className="mr-1 text-xs text-slate-500">用示例填充</span>
      {FORM_TEMPLATES.map((template) => {
        const isSelected = template.id === selectedTemplateId;
        return (
          <button
            key={template.id}
            type="button"
            onClick={() => onSelectTemplate(template.id)}
            title={template.description}
            aria-pressed={isSelected}
            className={`rounded border px-2.5 py-1 text-xs font-medium transition-colors ${
              isSelected
                ? 'border-ink bg-ink text-white'
                : 'border-slate-300 bg-sheet text-slate-700 hover:border-ink hover:text-ink'
            }`}
          >
            {template.label}
          </button>
        );
      })}
      {hasFormContent && (
        <button
          type="button"
          onClick={onClear}
          className="rounded px-2.5 py-1 text-xs text-slate-500 underline-offset-2 transition-colors hover:text-mark hover:underline"
        >
          清空表单
        </button>
      )}
    </div>
  );
}
