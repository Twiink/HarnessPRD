import { Check, Loader2 } from 'lucide-react';

export type StepItem = {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'done';
};

export type GenerationStepperProps = {
  steps: StepItem[];
  elapsedSeconds: number;
  hint?: string;
};

export default function GenerationStepper({
  steps,
  elapsedSeconds,
  hint,
}: GenerationStepperProps) {
  if (steps.length === 0) return null;

  return (
    <div className="flex-shrink-0 border-b border-hair bg-primary-50/60 px-6 py-2.5 lg:px-8" role="status">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ol className="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm">
          {steps.map((step, index) => (
            <li key={step.id} className="flex items-center gap-1">
              {index > 0 && <span className="mx-1.5 h-px w-5 bg-rule" aria-hidden />}
              <span
                className={`flex items-center gap-1.5 ${
                  step.status === 'active'
                    ? 'font-medium text-primary-700'
                    : step.status === 'done'
                      ? 'text-ink'
                      : 'text-slate-400'
                }`}
              >
                {step.status === 'active' && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
                {step.status === 'done' && <Check className="h-3.5 w-3.5 text-primary-600" aria-hidden />}
                {step.status === 'pending' && (
                  <span className="h-2 w-2 rounded-full border border-slate-400" aria-hidden />
                )}
                {step.label}
              </span>
            </li>
          ))}
        </ol>
        <span className="font-cond text-sm font-medium tabular-nums text-slate-600">
          已用 {elapsedSeconds} 秒
        </span>
      </div>
      {hint && <p className="mt-1.5 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}
