type ClarificationWarnBannerProps = {
  visible?: boolean;
};

export default function ClarificationWarnBanner({ visible }: ClarificationWarnBannerProps) {
  if (!visible) return null;

  return (
    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      已讨论较多内容。若无更多补充，可以结束澄清并生成 PRD。
    </div>
  );
}
