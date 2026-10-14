import type { TextareaHTMLAttributes } from 'react';

export function FieldLabel({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-2 space-y-1">
      <div className="text-sm font-medium text-slate-800">{title}</div>
      {hint && <div className="text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500 ${props.className || ''}`}
    />
  );
}
