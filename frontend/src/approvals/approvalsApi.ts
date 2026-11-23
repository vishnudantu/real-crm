import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  ApprovalCreatePayload,
  ApprovalDecisionPayload,
  ApprovalListResponse,
  ApprovalRequestItem,
  ApprovalStatus,
} from "./approvalsModel";
import { offsetForPage } from "./approvalsModel";

const SESSION = { getToken: getSession, clearToken: clearSession };
const id = (value: string): string => encodeURIComponent(value);

export const approvalKeys = {
  all: ["admin", "approvals"] as const,
  list: (page: number, pageSize: number, status: ApprovalStatus | "ALL", requestType: string) =>
    [...approvalKeys.all, "list", page, pageSize, status, requestType] as const,
  detail: (requestId: string) => [...approvalKeys.all, "detail", requestId] as const,
};

export interface FetchApprovalsParams {
  page: number;
  pageSize: number;
  status: ApprovalStatus | "ALL";
  requestType: string;
}

/** GET /approvals/requests — newest first, filtered by status and type. */
export function fetchApprovals(params: FetchApprovalsParams): Promise<ApprovalListResponse> {
  const query = new URLSearchParams({
    limit: String(params.pageSize),
    offset: String(offsetForPage(params.page, params.pageSize)),
  });
  if (params.status !== "ALL") query.set("status", params.status);
  if (params.requestType.trim()) query.set("request_type", params.requestType.trim());
  return bearerRequest<ApprovalListResponse>(`/approvals/requests?${query}`, SESSION);
}

/** POST /approvals/requests — opens a pending request for any entity reference. */
export function createApprovalRequest(payload: ApprovalCreatePayload): Promise<ApprovalRequestItem> {
  return bearerRequest<ApprovalRequestItem>("/approvals/requests", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** POST /approvals/requests/{id}/decision — ADMIN only, self-decision blocked server-side. */
export function decideApprovalRequest(
  requestId: string,
  payload: ApprovalDecisionPayload,
): Promise<ApprovalRequestItem> {
  return bearerRequest<ApprovalRequestItem>(
    `/approvals/requests/${id(requestId)}/decision`,
    SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

/** POST /approvals/requests/{id}/cancel — requester or admin, pending only. */
export function cancelApprovalRequest(requestId: string): Promise<ApprovalRequestItem> {
  return bearerRequest<ApprovalRequestItem>(
    `/approvals/requests/${id(requestId)}/cancel`,
    SESSION,
    { method: "POST" },
  );
}
