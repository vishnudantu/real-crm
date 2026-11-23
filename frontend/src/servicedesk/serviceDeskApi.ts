import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  AgentSuggestion,
  CsatPeriod,
  CsatStats,
  KbArticleCreatePayload,
  KbArticleItem,
  KbArticleListResponse,
  KbArticleStatus,
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

export const kbKeys = {
  all: ["admin", "service-desk", "kb"] as const,
  list: (page: number, pageSize: number, status: KbArticleStatus | "ALL", search: string) =>
    [...kbKeys.all, "list", page, pageSize, status, search] as const,
  suggestions: (ticketId: string) => [...kbKeys.all, "suggestions", ticketId] as const,
};

export const csatKeys = {
  all: ["admin", "service-desk", "csat"] as const,
  stats: (period: CsatPeriod) => [...csatKeys.all, "stats", period] as const,
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

/** GET /service-desk/tickets/{id}/suggestions — top-3 published KB articles. */
export function fetchTicketSuggestions(ticketId: string): Promise<AgentSuggestion[]> {
  return bearerRequest<AgentSuggestion[]>(
    `/service-desk/tickets/${id(ticketId)}/suggestions`,
    SESSION,
  );
}

/** GET /service-desk/stats/csat — average CSAT + ticket trends for the board. */
export function fetchCsatStats(period: CsatPeriod): Promise<CsatStats> {
  return bearerRequest<CsatStats>(`/service-desk/stats/csat?period=${period}`, SESSION);
}

/** POST /service-desk/kb/articles — staff draft creation. */
export function createKbArticle(payload: KbArticleCreatePayload): Promise<KbArticleItem> {
  return bearerRequest<KbArticleItem>("/service-desk/kb/articles", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface FetchKbArticlesParams {
  page: number;
  pageSize: number;
  status: KbArticleStatus | "ALL";
  search: string;
}

/** GET /service-desk/kb/articles — staff list over all statuses. */
export function fetchKbArticles(
  params: FetchKbArticlesParams,
): Promise<KbArticleListResponse> {
  const query = new URLSearchParams({
    limit: String(params.pageSize),
    offset: String(offsetForPage(params.page, params.pageSize)),
  });
  if (params.status !== "ALL") query.set("status", params.status);
  if (params.search.trim()) query.set("search", params.search.trim());
  return bearerRequest<KbArticleListResponse>(`/service-desk/kb/articles?${query}`, SESSION);
}

/** POST /service-desk/kb/articles/{id}/publish — makes it buyer-visible. */
export function publishKbArticle(articleId: string): Promise<KbArticleItem> {
  return bearerRequest<KbArticleItem>(`/service-desk/kb/articles/${id(articleId)}/publish`, SESSION, {
    method: "POST",
  });
}
