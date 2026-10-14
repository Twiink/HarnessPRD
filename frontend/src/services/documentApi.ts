import axios from 'axios';
import type {
  CheckpointResponse,
  DocumentSlotSummary,
  DocumentType,
  DocumentVersionDetail,
  RestoreResponse,
  UpdateVersionNoteResponse,
  VersionListResponse,
} from '../types/document';

const apiClient = axios.create({
  baseURL: '/api/session',
  headers: { 'Content-Type': 'application/json' },
});

function parseApiError(err: unknown, fallback: string): Error {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return new Error(detail);
    }
    if (err.response?.status === 404) {
      return new Error('方案或历史记录不存在');
    }
    if (err.response?.status === 400) {
      return new Error(typeof detail === 'string' ? detail : '请求无效');
    }
  }
  return new Error(fallback);
}

export async function fetchDocumentSlots(sessionId: string): Promise<DocumentSlotSummary[]> {
  try {
    const res = await apiClient.get<{ items: DocumentSlotSummary[] }>(`/${sessionId}/documents`);
    return res.data.items;
  } catch (err) {
    throw parseApiError(err, '加载文档槽位失败');
  }
}

export async function fetchVersionList(
  sessionId: string,
  docType: DocumentType,
): Promise<VersionListResponse> {
  try {
    const res = await apiClient.get<VersionListResponse>(`/${sessionId}/documents/${docType}/versions`);
    return res.data;
  } catch (err) {
    throw parseApiError(err, '加载历史记录失败');
  }
}

export async function fetchVersionDetail(
  sessionId: string,
  docType: DocumentType,
  versionId: string,
): Promise<DocumentVersionDetail> {
  try {
    const res = await apiClient.get<DocumentVersionDetail>(
      `/${sessionId}/documents/${docType}/versions/${versionId}`,
    );
    return res.data;
  } catch (err) {
    throw parseApiError(err, '加载历史详情失败');
  }
}

export async function checkpointVersion(
  sessionId: string,
  docType: DocumentType,
  body?: { content?: string; change_note?: string },
): Promise<CheckpointResponse> {
  try {
    const res = await apiClient.post<CheckpointResponse>(
      `/${sessionId}/documents/${docType}/versions/checkpoint`,
      body ?? {},
    );
    return res.data;
  } catch (err) {
    throw parseApiError(err, '保存快照失败');
  }
}

export async function restoreVersion(
  sessionId: string,
  docType: DocumentType,
  versionId: string,
): Promise<RestoreResponse> {
  try {
    const res = await apiClient.post<RestoreResponse>(
      `/${sessionId}/documents/${docType}/versions/${versionId}/restore`,
    );
    return res.data;
  } catch (err) {
    throw parseApiError(err, '恢复此记录失败');
  }
}

export async function updateVersionNote(
  sessionId: string,
  docType: DocumentType,
  versionId: string,
  changeNote: string,
): Promise<UpdateVersionNoteResponse> {
  try {
    const res = await apiClient.patch<UpdateVersionNoteResponse>(
      `/${sessionId}/documents/${docType}/versions/${versionId}/note`,
      { change_note: changeNote },
    );
    return res.data;
  } catch (err) {
    throw parseApiError(err, '保存备注失败');
  }
}
