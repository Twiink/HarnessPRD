import { useCallback, useEffect, useState } from 'react';
import {
  checkpointVersion,
  fetchVersionDetail,
  fetchVersionList,
  restoreVersion,
  updateVersionNote,
} from '../services/documentApi';
import type { DocumentType, DocumentVersionDetail, DocumentVersionListItem } from '../types/document';

type UseDocumentVersionsArgs = {
  sessionId: string | undefined;
  docType: DocumentType;
  editorContent: string;
  enabled: boolean;
};

type UseDocumentVersionsReturn = {
  versions: DocumentVersionListItem[];
  currentVersionNo: number | null;
  currentVersionId: string | null;
  preview: DocumentVersionDetail | null;
  previewVersionId: string | null;
  activeVersionReview: DocumentVersionDetail['metadata']['review'] | null;
  activeVersionLabel: string | null;
  activeDetail: DocumentVersionDetail | null;
  isLoadingList: boolean;
  isLoadingPreview: boolean;
  isLoadingCurrentDetail: boolean;
  isCheckpointing: boolean;
  isRestoring: boolean;
  savingNoteVersionId: string | null;
  error: string | null;
  refreshList: () => Promise<void>;
  openPreview: (versionId: string) => Promise<void>;
  closePreview: () => void;
  checkpoint: () => Promise<void>;
  restorePreview: () => Promise<string | null>;
  saveVersionNote: (versionId: string, changeNote: string) => Promise<void>;
};

export function useDocumentVersions({
  sessionId,
  docType,
  editorContent,
  enabled,
}: UseDocumentVersionsArgs): UseDocumentVersionsReturn {
  const [versions, setVersions] = useState<DocumentVersionListItem[]>([]);
  const [currentVersionNo, setCurrentVersionNo] = useState<number | null>(null);
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
  const [currentVersionDetail, setCurrentVersionDetail] = useState<DocumentVersionDetail | null>(null);
  const [preview, setPreview] = useState<DocumentVersionDetail | null>(null);
  const [previewVersionId, setPreviewVersionId] = useState<string | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isLoadingCurrentDetail, setIsLoadingCurrentDetail] = useState(false);
  const [isCheckpointing, setIsCheckpointing] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [savingNoteVersionId, setSavingNoteVersionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    if (!sessionId || !enabled) return;
    setIsLoadingList(true);
    setError(null);
    try {
      const data = await fetchVersionList(sessionId, docType);
      setVersions(data.versions);
      const current = data.versions.find((v) => v.is_current);
      setCurrentVersionNo(current?.version_no ?? null);
      setCurrentVersionId(current?.id ?? null);

      if (current?.id) {
        setIsLoadingCurrentDetail(true);
        try {
          const detail = await fetchVersionDetail(sessionId, docType, current.id);
          setCurrentVersionDetail(detail);
        } catch {
          setCurrentVersionDetail(null);
        } finally {
          setIsLoadingCurrentDetail(false);
        }
      } else {
        setCurrentVersionDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载版本列表失败');
    } finally {
      setIsLoadingList(false);
    }
  }, [sessionId, docType, enabled]);

  useEffect(() => {
    if (enabled && sessionId) {
      void refreshList();
    }
  }, [enabled, sessionId, docType, refreshList]);

  const closePreview = useCallback(() => {
    setPreview(null);
    setPreviewVersionId(null);
  }, []);

  const openPreview = useCallback(
    async (versionId: string) => {
      if (!sessionId) return;
      const current = versions.find((v) => v.is_current);
      if (current?.id === versionId) {
        closePreview();
        return;
      }
      setIsLoadingPreview(true);
      setError(null);
      try {
        const detail = await fetchVersionDetail(sessionId, docType, versionId);
        setPreview(detail);
        setPreviewVersionId(versionId);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载版本详情失败');
      } finally {
        setIsLoadingPreview(false);
      }
    },
    [sessionId, docType, versions, closePreview],
  );

  const checkpoint = useCallback(
    async () => {
      if (!sessionId) return;
      setIsCheckpointing(true);
      setError(null);
      try {
        await checkpointVersion(sessionId, docType, {
          content: editorContent,
        });
        await refreshList();
        closePreview();
      } catch (err) {
        setError(err instanceof Error ? err.message : '保存为新版本失败');
        throw err;
      } finally {
        setIsCheckpointing(false);
      }
    },
    [sessionId, docType, editorContent, refreshList, closePreview],
  );

  const saveVersionNote = useCallback(
    async (versionId: string, changeNote: string) => {
      if (!sessionId) return;
      setSavingNoteVersionId(versionId);
      setError(null);
      try {
        const result = await updateVersionNote(sessionId, docType, versionId, changeNote);
        setVersions((prev) =>
          prev.map((version) =>
            version.id === versionId
              ? {
                  ...version,
                  change_note: result.change_note ?? null,
                }
              : version,
          ),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : '保存备注失败');
        throw err;
      } finally {
        setSavingNoteVersionId(null);
      }
    },
    [sessionId, docType],
  );

  const restorePreview = useCallback(async (): Promise<string | null> => {
    if (!sessionId || !previewVersionId) return null;
    setIsRestoring(true);
    setError(null);
    try {
      const result = await restoreVersion(sessionId, docType, previewVersionId);
      closePreview();
      await refreshList();
      return result.content;
    } catch (err) {
      setError(err instanceof Error ? err.message : '恢复此版本失败');
      throw err;
    } finally {
      setIsRestoring(false);
    }
  }, [sessionId, docType, previewVersionId, closePreview, refreshList]);

  const activeDetail = preview ?? currentVersionDetail;
  const activeVersionReview = activeDetail?.metadata?.review ?? null;
  const activeVersionLabel = activeDetail ? `v${activeDetail.version_no}` : null;

  return {
    versions,
    currentVersionNo,
    currentVersionId,
    preview,
    previewVersionId,
    activeVersionReview,
    activeVersionLabel,
    activeDetail,
    isLoadingList,
    isLoadingPreview,
    isLoadingCurrentDetail,
    isCheckpointing,
    isRestoring,
    savingNoteVersionId,
    error,
    refreshList,
    openPreview,
    closePreview,
    checkpoint,
    restorePreview,
    saveVersionNote,
  };
}
