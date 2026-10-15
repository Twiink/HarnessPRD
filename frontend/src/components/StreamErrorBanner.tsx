import { AlertCircle } from 'lucide-react';

type StreamErrorBannerProps = {
  message: string;
  requestId?: string | null;
  onCopyRequestId?: () => void;
  className?: string;
};

export default function StreamErrorBanner({
  message,
  requestId,
  onCopyRequestId,
  className = '',
}: StreamErrorBannerProps) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className={`flex items-start gap-2.5 rounded border border-mark/40 bg-red-50 px-4 py-3 text-sm text-mark ${className}`}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>
        <div>{message}</div>
        {requestId && onCopyRequestId && (
          <button
            type="button"
            onClick={() => onCopyRequestId()}
            className="mt-1.5 text-xs font-medium underline underline-offset-2 hover:no-underline"
          >
            复制请求 ID，便于排查
          </button>
        )}
      </div>
    </div>
  );
}
