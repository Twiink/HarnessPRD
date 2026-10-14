export function resolveCurrentVersionNo(
  list: {
    current_version_id: string | null;
    current_version_no?: number | null;
    versions: { id: string; version_no: number; is_current?: boolean }[];
  },
): number | null {
  if (list.current_version_no != null) return list.current_version_no;
  if (list.current_version_id) {
    const match = list.versions.find((v) => v.id === list.current_version_id);
    if (match) return match.version_no;
  }
  const current = list.versions.find((v) => v.is_current);
  return current?.version_no ?? null;
}
export function formatDocumentHistoryTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '历史记录';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}
