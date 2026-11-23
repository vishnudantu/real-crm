import { clearSession, getSession } from "../../auth/session";
import { bearerRequest } from "../../shared/apiRequest";
import type { TicketSatisfaction } from "../../servicedesk/serviceDeskModel";
import type {
  BuyerTicketDetail,
  BuyerTicketListResponse,
  HelpArticle,
  HelpArticleListResponse,
} from "./helpCenterModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const helpKeys = {
  all: ["buyer", "help"] as const,
  articles: (search: string) => [...helpKeys.all, "articles", search] as const,
  tickets: () => [...helpKeys.all, "tickets"] as const,
  ticket: (ticketId: string) => [...helpKeys.all, "ticket", ticketId] as const,
};

/**
 * Buyer portal routes on /service-desk/help/* and /service-desk/mine/tickets*.
 * Help-center reads are tenant + PUBLISHED scoped server-side; the ticket and
 * CSAT routes resolve the buyer's Contact from the authenticated session
 * (never from the request), so foreign or unresolvable resources answer 404.
 */

export function fetchHelpArticles(params: { search?: string } = {}): Promise<HelpArticleListResponse> {
  const query = new URLSearchParams({ limit: "100", offset: "0" });
  if (params.search) query.set("search", params.search);
  return bearerRequest<HelpArticleListResponse>(`/service-desk/help/articles?${query}`, SESSION);
}

export function fetchHelpArticle(articleId: string): Promise<HelpArticle> {
  return bearerRequest<HelpArticle>(
    `/service-desk/help/articles/${encodeURIComponent(articleId)}`,
    SESSION,
  );
}

export function fetchMyTickets(): Promise<BuyerTicketListResponse> {
  return bearerRequest<BuyerTicketListResponse>("/service-desk/mine/tickets?limit=100", SESSION);
}

export function fetchMyTicket(ticketId: string): Promise<BuyerTicketDetail> {
  return bearerRequest<BuyerTicketDetail>(
    `/service-desk/mine/tickets/${encodeURIComponent(ticketId)}`,
    SESSION,
  );
}

export interface CsatSubmission {
  ticketId: string;
  rating: number;
  feedback: string | null;
}

/** PUT replaces the buyer's rating for their own closed ticket. */
export function submitTicketSatisfaction(input: CsatSubmission): Promise<TicketSatisfaction> {
  return bearerRequest<TicketSatisfaction>(
    `/service-desk/mine/tickets/${encodeURIComponent(input.ticketId)}/satisfaction`,
    SESSION,
    {
      method: "PUT",
      body: JSON.stringify({ rating: input.rating, feedback: input.feedback }),
    },
  );
}
