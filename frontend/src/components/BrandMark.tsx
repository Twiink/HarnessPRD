type BrandMarkProps = {
  className?: string;
};

/** ReqFlow 字标：窄体字母 + 一段制图标注线 */
export default function BrandMark({ className = '' }: BrandMarkProps) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden className="shrink-0">
        <rect x="0.75" y="0.75" width="16.5" height="16.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 12.5 L8 8.5 L10.5 11 L14 5.5" fill="none" stroke="#1f5fa8" strokeWidth="1.75" />
        <circle cx="14" cy="5.5" r="1.4" fill="#1f5fa8" />
      </svg>
      <span className="font-cond text-[20px] font-semibold leading-none tracking-[0.01em]">ReqFlow</span>
    </span>
  );
}
