import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';

export function FormCollapsibleSection({
  title,
  description,
  defaultOpen = true,
  children,
}: {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 hover:bg-slate-50/80 [&::-webkit-details-marker]:hidden">
        <div>
          <div className="text-sm font-semibold text-slate-900">{title}</div>
          {description && <div className="mt-0.5 text-xs text-slate-500">{description}</div>}
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-5 border-t border-slate-100 px-5 py-5">{children}</div>
    </details>
  );
}

export function FieldLabel({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="space-y-1">
      <div className="text-sm font-medium text-gray-800">{title}</div>
      {hint && <div className="text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <div className="mt-1 text-xs text-red-600">{message}</div>;
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return (
    <input
      {...rest}
      className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`}
    />
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return (
    <textarea
      {...rest}
      className={`w-full resize-none rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`}
    />
  );
}

export function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return (
    <select
      {...rest}
      className={`w-full rounded-lg border bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${invalid ? 'border-red-300 focus:ring-red-200' : 'border-gray-200 focus:ring-primary-500'} ${className || ''}`}
    />
  );
}
