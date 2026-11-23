/** Public contracts and pure helpers for the buyer-facing document portal.
 *
 * Mirrors backend/app/modules/buyer_docs/schemas.py exactly. Timestamps are
 * ISO strings on the wire; UUIDs are strings.
 */

export type BuyerDocumentCategory =
  | "IDENTITY"
  | "ADDRESS"
  | "INCOME"
  | "BANK"
  | "LOAN"
  | "PROPERTY"
  | "AGREEMENT"
  | "PAYMENT"
  | "REGISTRATION"
  | "POSSESSION"
  | "OTHER";

export type BuyerDocumentStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "VERIFIED"
  | "REJECTED"
  | "EXPIRED";

export type DocumentRequestStatus = "OPEN" | "FULFILLED" | "CANCELLED";

export interface BuyerDocument {
  id: string;
  contact_id: string | null;
  category: BuyerDocumentCategory;
  title: string;
  content_sha256: string;
  content_type: string;
  size_bytes: number;
  status: BuyerDocumentStatus;
  uploaded_by_id: string | null;
  verified_by_id: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  expiry_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuyerDocumentListResponse {
  items: BuyerDocument[];
  total: number;
}

export interface DocumentRequest {
  id: string;
  contact_id: string;
  category: BuyerDocumentCategory;
  title: string;
  status: DocumentRequestStatus;
  due_date: string | null;
  notes: string | null;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentRequestListResponse {
  items: DocumentRequest[];
  total: number;
}

/** Max upload size — mirrors backend buyer_docs/storage.MAX_DOCUMENT_BYTES (10 MB). */
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;

/** Human-readable max size for the upload dialog note. */
export const MAX_DOCUMENT_SIZE_LABEL = "10 MB";

/**
 * Accepted upload types. The backend service only allows application/pdf and
 * image/* (see buyer_docs/service.upload_document). PNG is excluded from the
 * accept list hint only if we ever add compression that re-encodes to JPEG;
 * today we surface exactly what the backend accepts.
 */
export const ACCEPTED_DOCUMENT_TYPES = "application/pdf,image/*";

export const ACCEPTED_DOCUMENT_TYPES_LABEL = "PDF or image (JPG, PNG, HEIC…)";

export const BUYER_DOCUMENT_CATEGORIES: readonly {
  value: BuyerDocumentCategory;
  label: string;
}[] = [
  { value: "IDENTITY", label: "Identity proof" },
  { value: "ADDRESS", label: "Address proof" },
  { value: "INCOME", label: "Income proof" },
  { value: "BANK", label: "Bank statement" },
  { value: "LOAN", label: "Loan document" },
  { value: "PROPERTY", label: "Property document" },
  { value: "AGREEMENT", label: "Agreement" },
  { value: "PAYMENT", label: "Payment proof" },
  { value: "REGISTRATION", label: "Registration" },
  { value: "POSSESSION", label: "Possession" },
  { value: "OTHER", label: "Other" },
];

export function categoryLabel(category: string): string {
  return (
    BUYER_DOCUMENT_CATEGORIES.find((entry) => entry.value === category)?.label ??
    category
      .toLowerCase()
      .split("_")
      .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
      .join(" ")
  );
}

/** Tailwind classes for the document status badge. */
export function documentStatusTone(status: BuyerDocumentStatus | string): string {
  switch (status) {
    case "VERIFIED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "SUBMITTED":
    case "UNDER_REVIEW":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "REJECTED":
      return "border-rose-200 bg-rose-50 text-rose-800";
    case "EXPIRED":
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}

export function documentStatusLabel(status: BuyerDocumentStatus | string): string {
  switch (status) {
    case "SUBMITTED":
      return "Submitted";
    case "UNDER_REVIEW":
      return "Under review";
    case "VERIFIED":
      return "Verified";
    case "REJECTED":
      return "Rejected";
    case "EXPIRED":
      return "Expired";
    default:
      return status;
  }
}

export function requestStatusTone(status: DocumentRequestStatus | string): string {
  switch (status) {
    case "OPEN":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "FULFILLED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "CANCELLED":
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}

/** Human-readable byte size, e.g. "2.4 MB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
}

/** File extension from a MIME type, used for the download filename. */
export function extensionForContentType(contentType: string): string {
  const normalized = contentType.split(";")[0]?.trim().toLowerCase() ?? "";
  switch (normalized) {
    case "application/pdf":
      return "pdf";
    case "image/jpeg":
      return "jpg";
    case "image/png":
      return "png";
    case "image/webp":
      return "webp";
    case "image/gif":
      return "gif";
    case "image/heic":
      return "heic";
    case "image/heif":
      return "heif";
    default:
      return normalized.startsWith("image/")
        ? normalized.slice("image/".length) || "img"
        : "bin";
  }
}

/** Make a title safe to use as a download filename (without extension). */
export function sanitizeFilename(name: string): string {
  const cleaned = name
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^[-._]+|[-._]+$/g, "");
  return cleaned || "document";
}

export function downloadFilename(document: Pick<BuyerDocument, "title" | "content_type">): string {
  return `${sanitizeFilename(document.title)}.${extensionForContentType(document.content_type)}`;
}

/** Whether a document can still be downloaded (always true unless rejected). */
export function isDownloadable(document: Pick<BuyerDocument, "status">): boolean {
  return document.status !== "REJECTED";
}

/** Whether a request is still awaiting the buyer's upload. */
export function isOpenRequest(request: Pick<DocumentRequest, "status">): boolean {
  return request.status === "OPEN";
}

/**
 * Validate a picked file against the backend rules before upload. Returns an
 * error message, or null when the file is acceptable. Kept pure for unit tests.
 */
export function validateUploadFile(
  file: { type: string; size: number },
  maxBytes: number = MAX_DOCUMENT_BYTES,
): string | null {
  const normalized = file.type.split(";")[0]?.trim().toLowerCase() ?? "";
  const isPdf = normalized === "application/pdf";
  const isImage = normalized.startsWith("image/");
  if (!isPdf && !isImage) {
    return "Only PDF or image files can be uploaded.";
  }
  if (file.size <= 0) {
    return "This file is empty. Please choose another file.";
  }
  if (file.size > maxBytes) {
    return `This file is larger than ${formatBytes(maxBytes)}. Please choose a smaller file.`;
  }
  return null;
}

/** Whether an upload should run through client-side image compression. */
export function shouldCompress(contentType: string): boolean {
  return contentType.split(";")[0]?.trim().toLowerCase().startsWith("image/") ?? false;
}
