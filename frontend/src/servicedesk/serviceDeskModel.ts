/** Contracts and pure helpers for the service-desk admin workspace.
 *
 * Mirrors backend/app/modules/service_desk/{schemas.py,models.py,service.py}.
 * There is NO priority-update endpoint: priority is chosen at creation and
 * displayed/filtered afterwards. Status moves go through PATCH …/status and
 * the server enforces the transition table below (mirrored for UX only).
 */

export type TicketCategory = "PAYMENT" | "DEFECT" | "DOCUMENT" | "GENERAL";
export type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type TicketStatus =
  | "OPEN"
  | "IN_PROGRESS"
  | "WAITING_ON_CUSTOMER"
  | "RESOLVED"
  | "CLOSED";

export interface TicketItem {
  id: string;
  ticket_number: string;
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  contact_id: string | null;
  booking_id: string | null;
  assigned_to_id: string | null;
  created_by_id: string | null;
  sla_due_at: string;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketCommentItem {
  id: string;
  ticket_id: string;
  author_id: string | null;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export type KbArticleStatus = "DRAFT" | "PUBLISHED";

export interface TicketSatisfaction {
  id: string;
  ticket_id: string;
  rating: number | null;
  feedback: string | null;
  created_at: string;
  responded_at: string | null;
}

export interface TicketDetail extends TicketItem {
  comments: TicketCommentItem[];
  satisfaction: TicketSatisfaction | null;
}

export interface TicketListResponse {
  items: TicketItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TicketCreatePayload {
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
  contact_id?: string | null;
  booking_id?: string | null;
}

export const TICKET_CATEGORIES: readonly { value: TicketCategory; label: string }[] = [
  { value: "PAYMENT", label: "Payment" },
  { value: "DEFECT", label: "Defect" },
  { value: "DOCUMENT", label: "Document" },
  { value: "GENERAL", label: "General" },
];

export const TICKET_PRIORITIES: readonly { value: TicketPriority; label: string }[] = [
  { value: "URGENT", label: "Urgent" },
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

export const TICKET_STATUSES: readonly { value: TicketStatus; label: string }[] = [
  { value: "OPEN", label: "Open" },
  { value: "IN_PROGRESS", label: "In progress" },
  { value: "WAITING_ON_CUSTOMER", label: "Waiting on customer" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "CLOSED", label: "Closed" },
];

/** Mirror of service.ALLOWED_TRANSITIONS — server remains the authority. */
export const ALLOWED_TICKET_TRANSITIONS: Readonly<Record<TicketStatus, readonly TicketStatus[]>> = {
  OPEN: ["IN_PROGRESS", "WAITING_ON_CUSTOMER", "RESOLVED", "CLOSED"],
  IN_PROGRESS: ["WAITING_ON_CUSTOMER", "RESOLVED"],
  WAITING_ON_CUSTOMER: ["IN_PROGRESS", "RESOLVED"],
  RESOLVED: ["CLOSED"],
  CLOSED: [],
};

export const MAX_TICKET_SUBJECT_LENGTH = 255;
export const MAX_TICKET_DESCRIPTION_LENGTH = 20000;
export const MAX_TICKET_COMMENT_LENGTH = 4000;
export const MAX_RESOLUTION_NOTE_LENGTH = 20000;

/** Unresolved statuses the backend counts as SLA-breachable. */
export const BREACH_STATUSES: readonly TicketStatus[] = ["OPEN", "IN_PROGRESS"];

export function allowedNextStatuses(status: TicketStatus): readonly TicketStatus[] {
  return ALLOWED_TICKET_TRANSITIONS[status] ?? [];
}

export function ticketStatusLabel(status: TicketStatus | string): string {
  return TICKET_STATUSES.find((entry) => entry.value === status)?.label ?? status;
}

export function ticketCategoryLabel(category: TicketCategory | string): string {
  return TICKET_CATEGORIES.find((entry) => entry.value === category)?.label ?? category;
}

export function ticketPriorityLabel(priority: TicketPriority | string): string {
  return TICKET_PRIORITIES.find((entry) => entry.value === priority)?.label ?? priority;
}

export function ticketStatusTone(status: TicketStatus | string): string {
  switch (status) {
    case "OPEN":
      return "border-sky-200 bg-sky-50 text-sky-800";
    case "IN_PROGRESS":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "WAITING_ON_CUSTOMER":
      return "border-violet-200 bg-violet-50 text-violet-800";
    case "RESOLVED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
  }
}

export function ticketPriorityTone(priority: TicketPriority | string): string {
  switch (priority) {
    case "URGENT":
      return "border-rose-300 bg-rose-50 text-rose-800";
    case "HIGH":
      return "border-orange-200 bg-orange-50 text-orange-800";
    case "MEDIUM":
      return "border-amber-200 bg-amber-50 text-amber-800";
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/70";
  }
}

/** A ticket is breached while unresolved (OPEN/IN_PROGRESS) and past its SLA deadline. */
export function isSlaBreached(
  ticket: Pick<TicketItem, "status" | "sla_due_at">,
  nowMs: number = Date.now(),
): boolean {
  if (!BREACH_STATUSES.includes(ticket.status)) return false;
  const due = Date.parse(ticket.sla_due_at);
  return !Number.isNaN(due) && due < nowMs;
}

/** Human SLA countdown/overage label for list and detail rows. */
export function slaCountdownLabel(slaDueAt: string, nowMs: number = Date.now()): string {
  const due = Date.parse(slaDueAt);
  if (Number.isNaN(due)) return "SLA unavailable";
  const diffMs = due - nowMs;
  const absMinutes = Math.floor(Math.abs(diffMs) / 60000);
  const hours = Math.floor(absMinutes / 60);
  const minutes = absMinutes % 60;
  const duration =
    hours >= 24
      ? `${Math.floor(hours / 24)}d ${hours % 24}h`
      : hours > 0
        ? `${hours}h ${minutes}m`
        : `${minutes}m`;
  return diffMs >= 0 ? `Due in ${duration}` : `Overdue by ${duration}`;
}

export function offsetForPage(page: number, pageSize: number): number {
  return Math.max(0, (page - 1) * pageSize);
}

export function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

export interface TicketCreateFormState {
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
}

export type TicketCreateFormErrors = Partial<Record<keyof TicketCreateFormState, string>>;

export function emptyTicketCreateForm(): TicketCreateFormState {
  return { subject: "", description: "", category: "GENERAL", priority: "MEDIUM" };
}

/** Client mirror of TicketCreateRequest's Field constraints. */
export function validateTicketCreateForm(form: TicketCreateFormState): TicketCreateFormErrors {
  const errors: TicketCreateFormErrors = {};
  const subject = form.subject.trim();
  const description = form.description.trim();
  if (!subject) errors.subject = "A subject is required.";
  else if (subject.length > MAX_TICKET_SUBJECT_LENGTH) {
    errors.subject = `At most ${MAX_TICKET_SUBJECT_LENGTH} characters.`;
  }
  if (!description) errors.description = "Describe the issue so the desk can act on it.";
  else if (description.length > MAX_TICKET_DESCRIPTION_LENGTH) {
    errors.description = `At most ${MAX_TICKET_DESCRIPTION_LENGTH} characters.`;
  }
  return errors;
}

export function validateCommentBody(body: string): string | null {
  const trimmed = body.trim();
  if (!trimmed) return "Write a comment before sending.";
  if (trimmed.length > MAX_TICKET_COMMENT_LENGTH) {
    return `At most ${MAX_TICKET_COMMENT_LENGTH} characters.`;
  }
  return null;
}

// --------------------------------------------------------------------------- //
// Knowledge base + CSAT (mirrors backend service_desk schemas)
// --------------------------------------------------------------------------- //

export interface KbArticleItem {
  id: string;
  title: string;
  slug: string;
  body_markdown: string;
  category: string;
  status: KbArticleStatus;
  published_at: string | null;
  author_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface KbArticleListResponse {
  items: KbArticleItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface KbArticleCreatePayload {
  title: string;
  slug?: string | null;
  body_markdown: string;
  category: string;
}

export interface AgentSuggestion {
  article_id: string;
  title: string;
  slug: string;
  category: string;
  score: number;
}

export interface CsatPeriodStat {
  period: string;
  surveys: number;
  rated: number;
  average_rating: number | null;
}

export interface CsatTrendPoint {
  period: string;
  opened: number;
  closed: number;
}

export interface CsatStats {
  period: string;
  surveys: number;
  rated: number;
  average_rating: number | null;
  response_rate: number | null;
  rating_histogram: Record<string, number>;
  unresolved_tickets: number;
  periods: CsatPeriodStat[];
  ticket_trends: CsatTrendPoint[];
}

export const MAX_KB_TITLE_LENGTH = 255;
export const MAX_KB_BODY_LENGTH = 100000;
export const MAX_KB_CATEGORY_LENGTH = 64;
export const MAX_CSAT_FEEDBACK_LENGTH = 2000;

export interface KbArticleFormState {
  title: string;
  slug: string;
  category: string;
  body_markdown: string;
}

export type KbArticleFormErrors = Partial<Record<keyof KbArticleFormState, string>>;

export function emptyKbArticleForm(): KbArticleFormState {
  return { title: "", slug: "", category: "", body_markdown: "" };
}

/** Client mirror of KbArticleCreateRequest constraints (server is authority). */
export function validateKbArticleForm(form: KbArticleFormState): KbArticleFormErrors {
  const errors: KbArticleFormErrors = {};
  const title = form.title.trim();
  const category = form.category.trim();
  const body = form.body_markdown.trim();
  if (!title) errors.title = "A title is required.";
  else if (title.length > MAX_KB_TITLE_LENGTH) {
    errors.title = `At most ${MAX_KB_TITLE_LENGTH} characters.`;
  }
  if (!category) errors.category = "Pick or type a category.";
  else if (category.length > MAX_KB_CATEGORY_LENGTH) {
    errors.category = `At most ${MAX_KB_CATEGORY_LENGTH} characters.`;
  }
  if (!body) errors.body_markdown = "Write the article body in markdown.";
  else if (body.length > MAX_KB_BODY_LENGTH) {
    errors.body_markdown = `At most ${MAX_KB_BODY_LENGTH} characters.`;
  }
  const slug = form.slug.trim();
  if (slug && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    errors.slug = "Lowercase letters, digits and single hyphens only.";
  }
  return errors;
}

/** Derive the backend slug style from a title (client preview only). */
export function slugifyArticleTitle(title: string): string {
  const slug = title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\x20-\x7E]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/g, "");
  return slug || "article";
}

export function kbArticleStatusLabel(status: KbArticleStatus | string): string {
  return status === "PUBLISHED" ? "Published" : "Draft";
}

export function kbArticleStatusTone(status: KbArticleStatus | string): string {
  return status === "PUBLISHED"
    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
    : "border-amber-200 bg-amber-50 text-amber-800";
}

/** 1..5 CSAT stars; null/undefined renders as "not rated". */
export function csatStars(rating: number | null | undefined): string {
  if (rating === null || rating === undefined || rating < 1 || rating > 5) return "—";
  return `${"★".repeat(rating)}${"☆".repeat(5 - rating)}`;
}

/** Compact average label for the board card ("4.2 / 5" or "No ratings yet"). */
export function csatAverageLabel(average: number | null | undefined): string {
  if (average === null || average === undefined) return "No ratings yet";
  return `${average.toFixed(1)} / 5`;
}

/** Format the backend response ratio (0..1) as a percentage string. */
export function csatResponseRateLabel(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${Math.round(rate * 100)}%`;
}

export const CSAT_PERIODS: readonly { value: "30d" | "90d" | "365d"; label: string }[] = [
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "365d", label: "Last 12 months" },
];

export type CsatPeriod = (typeof CSAT_PERIODS)[number]["value"];
