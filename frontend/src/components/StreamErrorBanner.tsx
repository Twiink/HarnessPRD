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
      className={`rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 ${className}`}
    >
      <div>{message}</div>
      {requestId && onCopyRequestId && (
        <button
          type="button"
          onClick={() => onCopyRequestId()}
          className="mt-2 text-xs font-medium text-red-800 underline underline-offset-2 hover:text-red-900"
        >
          复制请求 ID
        </button>
      )}
    </div>
  );
}
