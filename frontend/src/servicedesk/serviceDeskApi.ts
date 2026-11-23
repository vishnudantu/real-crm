import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  TicketCommentItem,
  TicketCreatePayload,
  TicketDetail,
  TicketItem,
  TicketListResponse,
  TicketPriority,
  TicketStatus,
} from "./serviceDeskModel";
import { offsetForPage } from "./serviceDeskModel";

const SESSION = { getToken: getSession, clearToken: clearSession };
const id = (value: string): string => encodeURIComponent(value);

export const ticketKeys = {
  all: ["admin", "service-desk"] as const,
  list: (
    page: number,
    pageSize: number,
    status: TicketStatus | "ALL",
    priority: TicketPriority | "ALL",
    breachOnly: boolean,
    assignedToId: string | "ALL",
  ) =>
    [...ticketKeys.all, "list", page, pageSize, status, priority, breachOnly, assignedToId] as const,
  detail: (ticketId: string) => [...ticketKeys.all, "detail", ticketId] as const,
};

export interface FetchTicketsParams {
  page: number;
  pageSize: number;
  status: TicketStatus | "ALL";
  priority: TicketPriority | "ALL";
  breachOnly: boolean;
  /** Staff user id to filter the queue by assignee, or "ALL". */
  assignedToId: string | "ALL";
}

/** GET /service-desk/tickets — newest first with status/priority/breach filters. */
export function fetchTickets(params: FetchTicketsParams): Promise<TicketListResponse> {
  const query = new URLSearchParams({
    limit: String(params.pageSize),
    offset: String(offsetForPage(params.page, params.pageSize)),
  });
  if (params.status !== "ALL") query.set("status", params.status);
  if (params.priority !== "ALL") query.set("priority", params.priority);
  if (params.breachOnly) query.set("breach_only", "true");
  if (params.assignedToId !== "ALL") query.set("assigned_to_id", params.assignedToId);
  return bearerRequest<TicketListResponse>(`/service-desk/tickets?${query}`, SESSION);
}

/** GET /service-desk/tickets/{id} — ticket plus its comment thread. */
export function fetchTicket(ticketId: string): Promise<TicketDetail> {
  return bearerRequest<TicketDetail>(`/service-desk/tickets/${id(ticketId)}`, SESSION);
}

/** POST /service-desk/tickets — priority is set HERE only (no update endpoint). */
export function createTicket(payload: TicketCreatePayload): Promise<TicketItem> {
  return bearerRequest<TicketItem>("/service-desk/tickets", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addTicketComment(
  ticketId: string,
  body: string,
  isInternal: boolean,
): Promise<TicketCommentItem> {
  return bearerRequest<TicketCommentItem>(
    `/service-desk/tickets/${id(ticketId)}/comments`,
    SESSION,
    { method: "POST", body: JSON.stringify({ body, is_internal: isInternal }) },
  );
}

export function updateTicketStatus(
  ticketId: string,
  status: TicketStatus,
  resolutionNote: string | null,
): Promise<TicketItem> {
  return bearerRequest<TicketItem>(`/service-desk/tickets/${id(ticketId)}/status`, SESSION, {
    method: "PATCH",
    body: JSON.stringify({ status, resolution_note: resolutionNote }),
  });
}

export function assignTicket(ticketId: string, assignedToId: string): Promise<TicketItem> {
  return bearerRequest<TicketItem>(`/service-desk/tickets/${id(ticketId)}/assign`, SESSION, {
    method: "POST",
    body: JSON.stringify({ assigned_to_id: assignedToId }),
  });
}
