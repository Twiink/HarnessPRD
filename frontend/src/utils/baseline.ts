export async function shortContentHash(content: string): Promise<string> {
  const data = new TextEncoder().encode(content);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 16);
}

export function shouldRevokeBaseline(params: {
  confirmed: boolean;
  confirmedVersionId: string | null | undefined;
  currentVersionId: string | null | undefined;
  confirmedContentHash: string | null | undefined;
  currentContentHash: string | null | undefined;
}): boolean {
  if (!params.confirmed) return false;
  if (
    params.confirmedVersionId &&
    params.currentVersionId &&
    params.confirmedVersionId !== params.currentVersionId
  ) {
    return true;
  }
  if (
    params.confirmedContentHash &&
    params.currentContentHash &&
    params.confirmedContentHash !== params.currentContentHash
  ) {
    return true;
  }
  return false;
}
