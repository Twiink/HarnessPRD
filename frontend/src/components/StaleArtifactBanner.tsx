import type { StaleWarning } from '../utils/staleArtifact';

type StaleArtifactBannerProps = {
  warnings: StaleWarning[];
};

export default function StaleArtifactBanner({ warnings }: StaleArtifactBannerProps) {
  if (!warnings.length) return null;

  return (
    <div className="mb-4 space-y-2">
      {warnings.map((warning, index) => (
        <div
          key={`${warning.message}-${index}`}
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        >
          <p>⚠ {warning.message}</p>
          {warning.actionLabel && warning.onAction && (
            <button
              type="button"
              className="shrink-0 rounded-md border border-amber-400 bg-white px-3 py-1 text-sm font-medium text-amber-900 hover:bg-amber-100"
              onClick={warning.onAction}
            >
              {warning.actionLabel}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
