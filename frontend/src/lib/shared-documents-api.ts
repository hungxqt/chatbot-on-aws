/**
 * Shared Documents API client (EFS cloud storage).
 */

import { apiClient, ApiError } from "./api-client";

export interface SharedDocument {
  id: string;
  filename: string;
  filesize: number;
  content_type: string;
  description: string | null;
  uploaded_by_id: string | null;
  uploaded_by_name: string | null;
  created_at: string;
}

export interface SharedDocumentList {
  items: SharedDocument[];
  total: number;
}

export async function listSharedDocuments(
  skip = 0,
  limit = 50,
): Promise<SharedDocumentList> {
  return apiClient.get<SharedDocumentList>("/shared-documents", {
    params: { skip: String(skip), limit: String(limit) },
  });
}

export async function uploadSharedDocument(
  file: File,
  description?: string,
): Promise<SharedDocument> {
  const formData = new FormData();
  formData.append("file", file);

  const params = description
    ? `?description=${encodeURIComponent(description)}`
    : "";
  const url = `/api/v1/shared-documents${params}`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new ApiError(response.status, error.detail || "Upload failed", error);
  }

  return response.json();
}

export function getSharedDocumentDownloadUrl(docId: string): string {
  return `/api/v1/shared-documents/${docId}/download`;
}

export async function deleteSharedDocument(docId: string): Promise<void> {
  return apiClient.delete(`/shared-documents/${docId}`);
}
