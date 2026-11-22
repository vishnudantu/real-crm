/** Public contracts and pure helpers for the documents admin workspace.
 *
 * Mirrors backend/app/modules/documents/schemas.py exactly. Timestamps are
 * ISO strings on the wire; UUIDs are strings.
 */

export type DocumentKind = "DEMAND_LETTER" | "RECEIPT" | "STATEMENT";

export type DocumentStatus = "DRAFT" | "ISSUED" | "VOIDED";

export type DocumentReferenceType = "installment" | "receipt";

export interface DocumentItem {
  id: string;
  kind: DocumentKind;
  reference_type: DocumentReferenceType | string;
  reference_id: string;
  template_id: string | null;
  template_version: number;
  document_number: string;
  status: DocumentStatus;
  content_sha256: string;
  issued_by: string | null;
  issued_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
}

export interface DocumentVoidRequest {
  reason: string;
}

export interface DocumentProof {
  id: string;
  document_number: string;
  content_sha256: string;
  status: DocumentStatus;
  template_version: number;
  issued_at: string | null;
  issued_by: string | null;
  voided_at: string | null;
  void_reason: string | null;
  payload_snapshot: Record<string, unknown>;
}

export const DOCUMENT_KINDS: readonly { value: DocumentKind; label: string }[] = [
  { value: "DEMAND_LETTER", label: "Demand letter" },
  { value: "RECEIPT", label: "Receipt" },
  { value: "STATEMENT", label: "Statement" },
];

export function isVoided(document: Pick<DocumentItem, "status">): boolean {
  return document.status === "VOIDED";
}

/** Tailwind classes for the status badge (ISSUED green, VOIDED muted). */
export function documentStatusTone(status: DocumentStatus | string): string {
  switch (status) {
    case "ISSUED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "VOIDED":
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
    case "DRAFT":
      return "border-amber-200 bg-amber-50 text-amber-800";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}

export function documentKindLabel(kind: string): string {
  return (
    DOCUMENT_KINDS.find((entry) => entry.value === kind)?.label ??
    kind
      .toLowerCase()
      .split("_")
      .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
      .join(" ")
  );
}

export function documentKindChipClass(kind: string): string {
  if (kind === "DEMAND_LETTER") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (kind === "RECEIPT") {
    return "border-teal-200 bg-teal-50 text-teal-800";
  }
  return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
}

/** Shortened reference for table cells: keeps head+tail of a UUID. */
export function shortReference(referenceId: string): string {
  if (!referenceId) return "—";
  if (referenceId.length <= 12) return referenceId;
  return `${referenceId.slice(0, 8)}…`;
}

/**
 * Make a document number safe to use as a download filename (without the
 * extension). Only letters, digits, dot, dash and underscore survive; runs of
 * anything else collapse to a single dash. Falls back to "document".
 */
export function sanitizeDocumentFilename(name: string): string {
  const cleaned = name
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^[-._]+|[-._]+$/g, "");
  return cleaned || "document";
}

export function documentDownloadFilename(documentNumber: string): string {
  return `${sanitizeDocumentFilename(documentNumber)}.pdf`;
}

/** A single human-readable field extracted from the issue-time snapshot. */
export interface ProofField {
  key: string;
  label: string;
  value: string;
}

interface ProofFieldSpec {
  key: string;
  label: string;
}

/** Key merge-context fields surfaced above the raw JSON in the proof drawer. */
export const PROOF_FIELD_SPECS: readonly ProofFieldSpec[] = [
  { key: "customer_name", label: "Customer" },
  { key: "unit_code", label: "Unit" },
  { key: "project_name", label: "Project" },
  { key: "rera_number", label: "RERA number" },
  { key: "milestone", label: "Milestone" },
  { key: "installment_number", label: "Installment" },
  { key: "amount", label: "Amount" },
  { key: "due_date", label: "Due date" },
  { key: "outstanding", label: "Outstanding" },
  { key: "receipt_number", label: "Receipt number" },
  { key: "channel", label: "Channel" },
  { key: "payment_reference", label: "Payment reference" },
  { key: "paid_date", label: "Paid date" },
  { key: "bank_name", label: "Bank" },
  { key: "bank_account_name", label: "Account name" },
  { key: "bank_account_number", label: "Account number (masked)" },
  { key: "bank_ifsc", label: "IFSC" },
];

function snapshotText(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return null;
}

/**
 * Extract the surfaced key fields from a payload snapshot. Tolerates a null /
 * undefined / non-object snapshot and skips absent or empty values, so a
 * demand letter never shows receipt-only rows and vice versa.
 */
export function extractProofFields(snapshot: unknown): ProofField[] {
  if (typeof snapshot !== "object" || snapshot === null || Array.isArray(snapshot)) {
    return [];
  }
  const record = snapshot as Record<string, unknown>;
  return PROOF_FIELD_SPECS.flatMap((spec): ProofField[] => {
    const value = snapshotText(record[spec.key]);
    return value === null ? [] : [{ key: spec.key, label: spec.label, value }];
  });
}

/** Pretty-print the raw snapshot for the collapsible evidence block. */
export function formatPayloadSnapshot(snapshot: unknown): string {
  if (snapshot === null || snapshot === undefined) return "{}";
  try {
    return JSON.stringify(snapshot, null, 2) ?? "{}";
  } catch {
    return "{}";
  }
}
