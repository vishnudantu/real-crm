/** Contracts and pure helpers for the buyer help center + CSAT widget.
 *
 * Mirrors backend/app/modules/service_desk/{schemas.py,router.py} buyer
 * surfaces (/service-desk/help/*, /service-desk/mine/tickets*). Search is a
 * simple case-insensitive substring match server-side; the client just
 * trims and enforces the 200-char query cap.
 */

import type { TicketSatisfaction } from "../../servicedesk/serviceDeskModel";

export interface HelpArticle {
  id: string;
  title: string;
  slug: string;
  body_markdown: string;
  category: string;
  status: "DRAFT" | "PUBLISHED";
  published_at: string | null;
  author_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface HelpArticleListResponse {
  items: HelpArticle[];
  total: number;
  limit: number;
  offset: number;
}

export interface BuyerTicketItem {
  id: string;
  ticket_number: string;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface BuyerTicketListResponse {
  items: BuyerTicketItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BuyerTicketDetail extends BuyerTicketItem {
  description: string;
  satisfaction: TicketSatisfaction | null;
}

export const MAX_HELP_QUERY_LENGTH = 200;
export const MAX_FEEDBACK_LENGTH = 2000;

export const CSAT_RATING_LABELS: Record<number, string> = {
  1: "Very unhappy",
  2: "Unhappy",
  3: "Okay",
  4: "Happy",
  5: "Very happy",
};

/** Normalize a help-center query: trim and cap, empty means "no search". */
export function normalizeHelpQuery(value: string): string {
  const trimmed = value.trim().slice(0, MAX_HELP_QUERY_LENGTH);
  return trimmed;
}

/** Validate a CSAT submission before hitting the API. */
export function validateCsatSubmission(
  rating: number | null,
  feedback: string,
): string | null {
  if (rating === null || rating < 1 || rating > 5 || !Number.isInteger(rating)) {
    return "Pick a rating from 1 to 5 stars.";
  }
  if (feedback.trim().length > MAX_FEEDBACK_LENGTH) {
    return `Please keep your note under ${MAX_FEEDBACK_LENGTH} characters.`;
  }
  return null;
}

/** Whether the CSAT widget should render for a ticket row. */
export function isRatingEligible(
  ticket: Pick<BuyerTicketDetail, "status"> | Pick<BuyerTicketItem, "status">,
): boolean {
  return ticket.status === "CLOSED";
}

/** Short markdown-ish renderer helper: paragraphs, ## headings, - list items.
 * Deliberately tiny (no dependency) — the portal shows staff-authored KB text. */
export function kbMarkdownBlocks(body: string): { type: "h2" | "p" | "li"; text: string }[] {
  const blocks: { type: "h2" | "p" | "li"; text: string }[] = [];
  for (const line of body.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("## ")) blocks.push({ type: "h2", text: trimmed.slice(3) });
    else if (/^[-*] /.test(trimmed)) blocks.push({ type: "li", text: trimmed.slice(2) });
    else blocks.push({ type: "p", text: trimmed });
  }
  return blocks;
}
