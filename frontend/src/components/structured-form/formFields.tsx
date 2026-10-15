import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';

export function FormCollapsibleSection({
  title,
  description,
  defaultOpen = true,
  index,
  children,
}: {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  /** 章节编号，对应表单在 PRD 中的分节 */
  index?: number;
  children: ReactNode;
}) {
  return (
    <details open={defaultOpen} className="group border-b border-hair last:border-b-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 transition-colors hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
        <div className="flex items-baseline gap-3">
          {index != null && (
            <span className="font-cond text-[15px] font-semibold text-primary-600">{index}</span>
          )}
          <div>
            <div className="text-[15px] font-semibold text-ink">{title}</div>
            {description && <div className="mt-0.5 text-xs text-slate-500">{description}</div>}
          </div>
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-5 px-6 pb-6 pt-1">{children}</div>
    </details>
  );
}

export function FieldLabel({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-1.5 space-y-0.5">
      <div className="text-sm font-medium text-ink">{title}</div>
      {hint && <div className="text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <div className="mt-1 text-xs text-mark">{message}</div>;
}

const fieldBase =
  'w-full rounded border bg-white px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:outline-none focus:ring-1';
const fieldState = (invalid?: boolean) =>
  invalid
    ? 'border-mark/60 focus:border-mark focus:ring-mark'
    : 'border-slate-300 focus:border-primary-600 focus:ring-primary-600';

export function TextInput(props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <input {...rest} className={`${fieldBase} ${fieldState(invalid)} ${className || ''}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return (
    <textarea
      {...rest}
      className={`${fieldBase} resize-none leading-relaxed ${fieldState(invalid)} ${className || ''}`}
    />
  );
}

export function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <select {...rest} className={`${fieldBase} ${fieldState(invalid)} ${className || ''}`} />;
}
