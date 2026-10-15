import type { TextareaHTMLAttributes } from 'react';

export function FieldLabel({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-2 space-y-0.5">
      <div className="text-sm font-medium text-ink">{title}</div>
      {hint && <div className="text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm leading-relaxed text-ink placeholder:text-slate-400 focus:border-primary-600 focus:outline-none focus:ring-1 focus:ring-primary-600 ${props.className || ''}`}
    />
  );
}
