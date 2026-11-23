/** Contracts and pure helpers for the approvals admin workspace.
 *
 * Mirrors backend/app/modules/approvals/{schemas.py,models.py} exactly:
 * statuses are PENDING/APPROVED/REJECTED/CANCELLED, amounts are paise,
 * ids and timestamps are strings on the wire.
 */

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";

export interface ApprovalRequestItem {
  id: string;
  request_type: string;
  reference_type: string;
  reference_id: string;
  requested_by_id: string | null;
  approver_id: string | null;
  status: ApprovalStatus;
  amount_paise: number | null;
  reason: string;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalListResponse {
  items: ApprovalRequestItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApprovalCreatePayload {
  request_type: string;
  reference_type: string;
  reference_id: string;
  reason: string;
  amount_paise?: number | null;
  approver_id?: string | null;
}

export interface ApprovalDecisionPayload {
  decision: Extract<ApprovalStatus, "APPROVED" | "REJECTED">;
  note?: string | null;
}

export const APPROVAL_STATUSES: readonly { value: ApprovalStatus; label: string }[] = [
  { value: "PENDING", label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
  { value: "CANCELLED", label: "Cancelled" },
];

/** request_type values with wired backend side effects, offered as presets. */
export const APPROVAL_TYPE_PRESETS: readonly {
  requestType: string;
  referenceType: string;
  label: string;
  takesAmount: boolean;
}[] = [
  { requestType: "SITE_VISIT_CAR", referenceType: "booking", label: "Site-visit car request", takesAmount: false },
  { requestType: "DISCOUNT", referenceType: "unit", label: "Unit discount", takesAmount: true },
  { requestType: "DEMAND_LETTER", referenceType: "document", label: "Demand letter release", takesAmount: false },
];

export const APPROVAL_REFERENCE_TYPES: readonly { value: string; label: string }[] = [
  { value: "booking", label: "Booking" },
  { value: "unit", label: "Unit" },
  { value: "document", label: "Document" },
];

export const MAX_APPROVAL_REASON_LENGTH = 2000;
export const MAX_APPROVAL_NOTE_LENGTH = 2000;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value.trim());
}

export function shortId(value: string | null): string {
  if (!value) return "—";
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

export function approvalStatusLabel(status: ApprovalStatus | string): string {
  return APPROVAL_STATUSES.find((entry) => entry.value === status)?.label ?? status;
}

/** Tailwind chip classes per approval status. */
export function approvalStatusTone(status: ApprovalStatus | string): string {
  switch (status) {
    case "PENDING":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "APPROVED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "REJECTED":
      return "border-rose-200 bg-rose-50 text-rose-700";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
  }
}

export function isPending(request: Pick<ApprovalRequestItem, "status">): boolean {
  return request.status === "PENDING";
}

/** A manager may decide only a pending request they did not raise themselves. */
export function canUserDecide(
  request: Pick<ApprovalRequestItem, "status" | "requested_by_id">,
  userId: string,
): boolean {
  return isPending(request) && request.requested_by_id !== userId;
}

/** Only the requester (or an admin, enforced server-side) may cancel, and only while pending. */
export function canUserCancel(
  request: Pick<ApprovalRequestItem, "status" | "requested_by_id">,
  userId: string,
  isAdmin: boolean,
): boolean {
  if (!isPending(request)) return false;
  return isAdmin || request.requested_by_id === userId;
}

export function offsetForPage(page: number, pageSize: number): number {
  return Math.max(0, (page - 1) * pageSize);
}

export function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

export interface ApprovalCreateFormState {
  requestType: string;
  referenceType: string;
  referenceId: string;
  reason: string;
  amountRupees: string;
  approverId: string;
}

export type ApprovalCreateFormErrors = Partial<
  Record<keyof ApprovalCreateFormState | "amount", string>
>;

export function emptyApprovalCreateForm(): ApprovalCreateFormState {
  return {
    requestType: "",
    referenceType: "booking",
    referenceId: "",
    reason: "",
    amountRupees: "",
    approverId: "",
  };
}

const RUPEES_PATTERN = /^\d+(\.\d{1,2})?$/;

/** Client mirror of ApprovalRequestCreate's Field constraints. */
export function validateApprovalCreateForm(
  form: ApprovalCreateFormState,
): ApprovalCreateFormErrors {
  const errors: ApprovalCreateFormErrors = {};
  const requestType = form.requestType.trim();
  const referenceId = form.referenceId.trim();
  const reason = form.reason.trim();

  if (!requestType) errors.requestType = "A request type is required.";
  else if (requestType.length > 48) errors.requestType = "At most 48 characters.";

  if (!form.referenceType) errors.referenceType = "Pick what this request refers to.";

  if (!referenceId) errors.referenceId = "The referenced record id is required.";
  else if (!isUuid(referenceId)) errors.referenceId = "Enter a valid UUID (36 characters).";

  if (!reason) errors.reason = "Explain why this needs approval.";
  else if (reason.length > MAX_APPROVAL_REASON_LENGTH) {
    errors.reason = `At most ${MAX_APPROVAL_REASON_LENGTH} characters.`;
  }

  const amount = form.amountRupees.trim();
  if (amount && !RUPEES_PATTERN.test(amount)) {
    errors.amountRupees = "Use digits, optional paise up to 2 decimals.";
  }
  if (form.approverId && !isUuid(form.approverId)) {
    errors.approverId = "Choose a valid approver from the list.";
  }
  return errors;
}

export function rupeesInputToPaise(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!RUPEES_PATTERN.test(trimmed)) return null;
  return Math.round(Number(trimmed) * 100);
}

/** Build the exact POST /approvals/requests body from a valid form. */
export function buildApprovalCreatePayload(form: ApprovalCreateFormState): ApprovalCreatePayload {
  const amountPaise = rupeesInputToPaise(form.amountRupees);
  return {
    request_type: form.requestType.trim(),
    reference_type: form.referenceType,
    reference_id: form.referenceId.trim(),
    reason: form.reason.trim(),
    ...(amountPaise === null ? {} : { amount_paise: amountPaise }),
    ...(form.approverId ? { approver_id: form.approverId } : {}),
  };
}
