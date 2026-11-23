import { API_BASE_URL, ApiError } from "../../auth/api";
import { clearSession, getSession } from "../../auth/session";
import type { StoredSession } from "../../auth/session";
import { bearerRequest } from "../../shared/apiRequest";
import type {
  BuyerDocument,
  BuyerDocumentCategory,
  BuyerDocumentListResponse,
  DocumentRequestListResponse,
} from "./buyerDocumentsModel";
import { downloadFilename } from "./buyerDocumentsModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const buyerDocumentKeys = {
  all: ["buyer", "documents"] as const,
  list: () => ["buyer", "documents", "list"] as const,
  requests: () => ["buyer", "documents", "requests"] as const,
};

/**
 * Buyer-scoped routes (/buyer-docs/mine/*). The backend resolves the
 * authenticated buyer to their contact server-side (email/phone match against
 * ContactMethod) and only ever returns that contact's own resources; anything
 * unresolvable or foreign returns 404. Client-passed contact ids are not
 * accepted on these routes.
 */

export function fetchBuyerDocuments(params: {
  category?: BuyerDocumentCategory;
} = {}): Promise<BuyerDocumentListResponse> {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return bearerRequest<BuyerDocumentListResponse>(
    `/buyer-docs/mine/documents${suffix}`,
    SESSION,
  );
}

export function fetchBuyerDocumentRequests(params: {
  category?: BuyerDocumentCategory;
} = {}): Promise<DocumentRequestListResponse> {
  // /mine/requests already returns only OPEN requests for this buyer.
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return bearerRequest<DocumentRequestListResponse>(
    `/buyer-docs/mine/requests${suffix}`,
    SESSION,
  );
}

export interface UploadBuyerDocumentInput {
  category: BuyerDocumentCategory;
  title: string;
  blob: Blob;
  contentType: string;
  expiryDate?: string;
}

/**
 * Raw-body upload (the backend reads request.body(), not multipart). The blob
 * has already been through client-side compression where applicable.
 */
export async function uploadBuyerDocument(
  input: UploadBuyerDocumentInput,
): Promise<BuyerDocument> {
  const session = getSession();
  if (!session?.accessToken) {
    throw new ApiError(401, "UNAUTHORIZED", "Active session required.");
  }
  const query = new URLSearchParams({
    category: input.category,
    title: input.title,
  });
  if (input.expiryDate) query.set("expiry_date", input.expiryDate);

  const response = await fetch(
    `${API_BASE_URL}/buyer-docs/mine/documents?${query.toString()}`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${session.accessToken}`,
        "Content-Type": input.contentType,
      },
      body: input.blob,
    },
  );
  if (!response.ok) {
    if (response.status === 401) clearSession();
    let message = "The document could not be uploaded. Please try again.";
    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null) {
        const record = body as Record<string, unknown>;
        if (typeof record.detail === "string" && record.detail) {
          message = record.detail;
        }
        const envelope = record.error;
        if (
          typeof envelope === "object" &&
          envelope !== null &&
          typeof (envelope as Record<string, unknown>).message === "string"
        ) {
          message = (envelope as Record<string, unknown>).message as string;
        }
      }
    } catch {
      // Non-JSON error body: keep the status-based message.
    }
    throw new ApiError(response.status, `HTTP_${response.status}`, message);
  }
  return (await response.json()) as BuyerDocument;
}

export interface BuyerDocumentDownloadResult {
  sha256: string;
  fileName: string;
}

/**
 * Authenticated download: bearer fetch -> object URL -> temporary anchor ->
 * revoke. The backend sets X-Content-Sha256 (evidence digest) on the response.
 */
export async function downloadBuyerDocument(
  document: Pick<BuyerDocument, "id" | "title" | "content_type">,
  token: StoredSession | string | null,
): Promise<BuyerDocumentDownloadResult> {
  const accessToken = typeof token === "string" ? token : token?.accessToken;
  if (!accessToken) {
    throw new ApiError(401, "UNAUTHORIZED", "Active session required.");
  }

  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/buyer-docs/mine/documents/${document.id}/download`,
      {
        headers: {
          Accept: "*/*",
          Authorization: `Bearer ${accessToken}`,
        },
      },
    );
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "We couldn't reach PropFlow. Check your connection and try again.",
    );
  }

  if (!response.ok) {
    if (response.status === 401) clearSession();
    throw new ApiError(
      response.status,
      `HTTP_${response.status}`,
      "The document could not be downloaded. Please try again.",
    );
  }

  const sha256 = response.headers.get("X-Content-Sha256")?.trim() ?? "";
  const blob = await response.blob();
  const fileName = downloadFilename(document);
  const url = URL.createObjectURL(blob);
  try {
    const anchor = globalThis.document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    anchor.rel = "noopener";
    globalThis.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }

  return { sha256, fileName };
}
