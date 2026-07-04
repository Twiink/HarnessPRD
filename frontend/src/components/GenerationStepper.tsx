import { Loader2 } from 'lucide-react';

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
    <div className="flex-shrink-0 border-b border-gray-100 bg-slate-50 px-6 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center gap-2">
              {index > 0 && <span className="text-gray-300">→</span>}
              <span
                className={`flex items-center gap-1.5 ${
                  step.status === 'active'
                    ? 'font-medium text-primary-600'
                    : step.status === 'done'
                      ? 'text-green-700'
                      : 'text-gray-400'
                }`}
              >
                {step.status === 'active' && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                )}
                {step.status === 'done' && <span aria-hidden>✓</span>}
                {step.status === 'pending' && <span aria-hidden>○</span>}
                {step.label}
              </span>
            </div>
          ))}
        </div>
        <span className="text-sm text-gray-500">已等待 {elapsedSeconds}s</span>
      </div>
      {hint && <p className="mt-2 text-sm text-gray-500">{hint}</p>}
    </div>
  );
}
