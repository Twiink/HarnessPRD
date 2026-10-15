type ClarificationWarnBannerProps = {
  visible?: boolean;
};

export default function ClarificationWarnBanner({ visible }: ClarificationWarnBannerProps) {
  if (!visible) return null;

  return (
    <div className="mb-3 rounded border border-stamp/50 bg-amber-50 px-4 py-2.5 text-sm text-amber-950">
      对话已经比较长了。没有新的补充的话，可以结束澄清并生成 PRD。
    </div>
  );
}
