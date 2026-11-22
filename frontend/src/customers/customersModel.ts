export type ContactStatus = "ACTIVE" | "MERGED" | "ANONYMIZED";
export type ContactMethodKind = "EMAIL" | "PHONE" | "WHATSAPP_ID" | "INSTAGRAM_HANDLE" | "MESSENGER_HANDLE";
export type VerificationState = "UNVERIFIED" | "VERIFIED" | "INVALID";
export type OpportunityStage = "NEW" | "CONTACTED" | "QUALIFIED" | "VISIT_SCHEDULED" | "VISITED" | "NEGOTIATING" | "BOOKED" | "WON" | "LOST" | "LOST_DORMANT";

export interface ContactMethod {
  id: string;
  kind: ContactMethodKind;
  value: string;
  normalized_value: string;
  verification_state: VerificationState;
  provenance: Record<string, unknown>;
  is_primary: boolean;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  canonical_key: string;
  display_name: string;
  primary_language: string;
  status: ContactStatus;
  notes: string | null;
  merged_into_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContactDetail extends Contact {
  methods: ContactMethod[];
}

export interface ContactListResponse {
  items: Contact[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ContactSearchPayload {
  email?: string | null;
  phone?: string | null;
  display_name?: string | null;
}

export interface ContactSearchResponse {
  exists: boolean;
  would_create: boolean;
  contact: Contact | null;
  matched_method: ContactMethod | null;
  normalized_email: string | null;
  normalized_phone: string | null;
}

export interface Opportunity {
  id: string;
  contact_id: string;
  project_id: string;
  lead_id: string | null;
  stage: OpportunityStage;
  owner_user_id: string | null;
  budget_min: number | null;
  budget_max: number | null;
  preferred_configuration: string | null;
  source: string | null;
  loss_reason: string | null;
  won_booking_id: string | null;
  value_paise: number | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type OpportunityUpdatePayload = Partial<Pick<Opportunity,
  "stage" | "owner_user_id" | "budget_min" | "budget_max" |
  "preferred_configuration" | "loss_reason" | "won_booking_id" | "value_paise"
>>;

export interface MergeEvidenceField {
  kind: string;
  value: string;
  normalized_value: string;
}

export interface DuplicateCandidate {
  contact_id: string;
  display_name: string;
  confidence: string;
  matched_fields: MergeEvidenceField[];
  evidence: string;
}

export interface DuplicateSuggestionsResponse {
  contact_id: string;
  candidates: DuplicateCandidate[];
}

export interface MergeResponse {
  id: string;
  survivor_id: string;
  merged_id: string;
  actor_user_id: string | null;
  reason: string | null;
  evidence: Record<string, unknown>;
  reverted_at: string | null;
  created_at: string;
}

export interface TimelineItem {
  type: string;
  occurred_at: string;
  actor: string | null;
  summary: string;
  link_ids: Record<string, string>;
}

export interface Customer360Response {
  contact: ContactDetail;
  opportunities: Opportunity[];
  timeline: TimelineItem[];
  freshness: Record<string, string | null>;
}

export interface TimelineDayGroup {
  dayKey: string;
  label: string;
  items: TimelineItem[];
}

export interface OpportunityStageGroup {
  stage: OpportunityStage | "OTHER";
  label: string;
  items: Opportunity[];
}

export interface MergeSummaryCounts {
  methodsMoved: number;
  methodsSkipped: number;
  opportunitiesRepointed: number;
}

export const OPPORTUNITY_STAGES: readonly OpportunityStage[] = [
  "NEW", "CONTACTED", "QUALIFIED", "VISIT_SCHEDULED", "VISITED",
  "NEGOTIATING", "BOOKED", "WON", "LOST", "LOST_DORMANT",
];

export const OPPORTUNITY_STAGE_LABELS: Readonly<Record<OpportunityStage, string>> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  VISIT_SCHEDULED: "Visit scheduled",
  VISITED: "Visited",
  NEGOTIATING: "Negotiating",
  BOOKED: "Booked",
  WON: "Won",
  LOST: "Lost",
  LOST_DORMANT: "Lost · dormant",
};

export function stageLabel(stage: string): string {
  return OPPORTUNITY_STAGE_LABELS[stage as OpportunityStage] ?? stage.replaceAll("_", " ").toLowerCase();
}

function newestFirst<T>(items: readonly T[], timestamp: (item: T) => string): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftTime = Date.parse(timestamp(left.item));
      const rightTime = Date.parse(timestamp(right.item));
      if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
        if (Number.isNaN(leftTime) && Number.isNaN(rightTime)) return left.index - right.index;
        return Number.isNaN(leftTime) ? 1 : -1;
      }
      return rightTime === leftTime ? left.index - right.index : rightTime - leftTime;
    })
    .map(({ item }) => item);
}

function timelineDayKey(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "unknown" : date.toISOString().slice(0, 10);
}

export function groupTimelineByDay(items: readonly TimelineItem[]): TimelineDayGroup[] {
  const groups = new Map<string, TimelineItem[]>();
  newestFirst(items, (item) => item.occurred_at).forEach((item) => {
    const key = timelineDayKey(item.occurred_at);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return Array.from(groups, ([dayKey, groupItems]) => {
    const date = new Date(`${dayKey}T00:00:00.000Z`);
    return {
      dayKey,
      label: dayKey === "unknown" ? "Date unavailable" : new Intl.DateTimeFormat("en-US", {
        weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC",
      }).format(date),
      items: groupItems,
    };
  });
}

export function groupOpportunitiesByStage(items: readonly Opportunity[]): OpportunityStageGroup[] {
  const known = OPPORTUNITY_STAGES.map((stage) => ({
    stage,
    label: OPPORTUNITY_STAGE_LABELS[stage],
    items: newestFirst(items.filter((item) => item.stage === stage), (item) => item.created_at),
  }));
  const otherItems = newestFirst(
    items.filter((item) => !OPPORTUNITY_STAGES.includes(item.stage)),
    (item) => item.created_at,
  );
  return otherItems.length > 0 ? [...known, { stage: "OTHER" as const, label: "Other stages", items: otherItems }] : known;
}

function evidenceCount(evidence: Readonly<Record<string, unknown>>, key: string): number {
  const value = evidence[key];
  return Array.isArray(value) ? value.length : 0;
}

export function mergeSummaryCounts(evidence: Readonly<Record<string, unknown>>): MergeSummaryCounts {
  return {
    methodsMoved: evidenceCount(evidence, "moved_method_ids"),
    methodsSkipped: evidenceCount(evidence, "skipped_method_ids"),
    opportunitiesRepointed: evidenceCount(evidence, "repointed_opportunity_ids"),
  };
}
