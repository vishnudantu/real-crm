import { API_BASE_URL, ApiError } from "../auth/api";
import { clearSession, getSession } from "../auth/session";
import type { StoredSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  DocumentItem,
  DocumentKind,
  DocumentListResponse,
  DocumentProof,
} from "./documentsModel";
import { documentDownloadFilename } from "./documentsModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const documentKeys = {
  all: ["admin", "documents"] as const,
  list: (kind: DocumentKind | "ALL", referenceId?: string) =>
    ["admin", "documents", { kind, referenceId: referenceId ?? null }] as const,
  proof: (documentId: string) =>
    ["admin", "documents", documentId, "proof"] as const,
};

export interface FetchDocumentsParams {
  kind?: DocumentKind | "ALL";
  referenceId?: string;
}

export function fetchDocuments(
  params: FetchDocumentsParams = {},
): Promise<DocumentListResponse> {
  const query = new URLSearchParams();
  if (params.kind && params.kind !== "ALL") query.set("kind", params.kind);
  if (params.referenceId?.trim()) {
    query.set("reference_id", params.referenceId.trim());
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return bearerRequest<DocumentListResponse>(`/documents${suffix}`, SESSION);
}

export function fetchDocument(documentId: string): Promise<DocumentItem> {
  return bearerRequest<DocumentItem>(`/documents/${documentId}`, SESSION);
}

export function fetchDocumentProof(documentId: string): Promise<DocumentProof> {
  return bearerRequest<DocumentProof>(`/documents/${documentId}/proof`, SESSION);
}

export function issueDemandLetter(installmentId: string): Promise<DocumentItem> {
  return bearerRequest<DocumentItem>(
    `/documents/demand-letters/${installmentId}`,
    SESSION,
    { method: "POST" },
  );
}

export function issueReceiptPdf(receiptId: string): Promise<DocumentItem> {
  return bearerRequest<DocumentItem>(
    `/documents/receipts/${receiptId}/pdf`,
    SESSION,
    { method: "POST" },
  );
}

export function voidDocument(
  documentId: string,
  reason: string,
): Promise<DocumentItem> {
  return bearerRequest<DocumentItem>(`/documents/${documentId}/void`, SESSION, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export interface DocumentDownloadResult {
  sha256: string;
  fileName: string;
}

/**
 * Authenticated PDF download. The endpoint requires a bearer token, so a plain
 * anchor would be rejected; we fetch the bytes with the Authorization header,
 * stream them into an object URL, click a temporary anchor, then revoke it.
 *
 * The X-Document-Sha256 header is required: it is the evidence digest shown in
 * the toast so the downloaded file can be matched against the proof drawer.
 */
export async function downloadDocument(
  id: string,
  token: StoredSession | string | null,
  fileName: string,
): Promise<DocumentDownloadResult> {
  const accessToken =
    typeof token === "string" ? token : token?.accessToken;
  if (!accessToken) {
    throw new ApiError(401, "UNAUTHORIZED", "Active session required.");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/documents/${id}/download`, {
      headers: {
        Accept: "application/pdf",
        Authorization: `Bearer ${accessToken}`,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "We couldn't reach PropFlow. Check your connection and try again.",
    );
  }

  if (!response.ok) {
    if (response.status === 401) clearSession();
    let message = "The document could not be downloaded. Please try again.";
    if (response.status === 410) {
      message = "This document was voided and can no longer be downloaded.";
    }
    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null) {
        const record = body as Record<string, unknown>;
        const detail = record.detail;
        const error = record.error;
        if (typeof detail === "string" && detail) message = detail;
        if (
          typeof error === "object" &&
          error !== null &&
          typeof (error as Record<string, unknown>).message === "string"
        ) {
          message = (error as Record<string, unknown>).message as string;
        }
      }
    } catch {
      // Non-JSON error body: keep the status-based message.
    }
    throw new ApiError(response.status, `HTTP_${response.status}`, message);
  }

  const sha256 = response.headers.get("X-Document-Sha256")?.trim();
  if (!sha256) {
    throw new ApiError(
      response.status,
      "MISSING_DOCUMENT_HASH",
      "The download is missing its SHA-256 evidence header. Contact support before relying on this file.",
    );
  }

  const blob = await response.blob();
  const safeName = fileName.endsWith(".pdf")
    ? fileName
    : documentDownloadFilename(fileName);
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = safeName;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }

  return { sha256, fileName: safeName };
}
