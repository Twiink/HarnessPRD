import { AlertTriangle } from 'lucide-react';
import type { StaleWarning } from '../utils/staleArtifact';

type StaleArtifactBannerProps = {
  warnings: StaleWarning[];
};

export default function StaleArtifactBanner({ warnings }: StaleArtifactBannerProps) {
  if (!warnings.length) return null;

  return (
    <div className="space-y-2">
      {warnings.map((warning, index) => (
        <div
          key={`${warning.message}-${index}`}
          className="flex flex-wrap items-center justify-between gap-3 rounded border border-stamp/50 bg-amber-50 px-4 py-2.5 text-sm text-amber-950"
        >
          <p className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-stamp" aria-hidden />
            {warning.message}
          </p>
          {warning.actionLabel && warning.onAction && (
            <button type="button" className="btn-outline py-1" onClick={warning.onAction}>
              {warning.actionLabel}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
