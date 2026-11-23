import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  Contact,
  ContactCreatePayload,
  ContactCreateResponse,
  ContactListResponse,
  ContactSearchPayload,
  ContactSearchResponse,
  ContactUpdatePayload,
  Customer360Response,
  DuplicateSuggestionsResponse,
  MergeResponse,
  Opportunity,
  OpportunityListResponse,
  OpportunityUpdatePayload,
} from "./customersModel";

const SESSION = { getToken: getSession, clearToken: clearSession };
const id = (value: string): string => encodeURIComponent(value);

export const customerKeys = {
  all: ["admin", "customers"] as const,
  list: (page: number, pageSize: number, search: string) => [...customerKeys.all, "list", page, pageSize, search] as const,
  detail: (contactId: string) => [...customerKeys.all, "detail", contactId] as const,
  duplicates: (contactId: string) => [...customerKeys.all, "duplicates", contactId] as const,
  opportunities: (page: number, pageSize: number) => ["admin", "opportunities", page, pageSize] as const,
};

export function fetchCustomers(page = 1, pageSize = 20, search = ""): Promise<ContactListResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search.trim()) params.set("search", search.trim());
  return bearerRequest<ContactListResponse>(`/customers?${params}`, SESSION);
}

export function searchCustomer(payload: ContactSearchPayload): Promise<ContactSearchResponse> {
  return bearerRequest<ContactSearchResponse>("/customers/search", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * POST /customers/contacts — idempotent by normalized email/phone.
 * 201 returns created=true; 200 returns the existing contact with created=false.
 */
export function createContact(payload: ContactCreatePayload): Promise<ContactCreateResponse> {
  return bearerRequest<ContactCreateResponse>("/customers/contacts", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** PATCH /customers/contacts/{id} — display_name / primary_language / notes only. */
export function updateContact(
  contactId: string,
  payload: ContactUpdatePayload,
): Promise<Contact> {
  return bearerRequest<Contact>(`/customers/contacts/${id(contactId)}`, SESSION, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export interface OpportunityCreatePayload {
  project_id: string;
  from_lead_id?: string | null;
  owner_user_id?: string | null;
  budget_min?: number | null;
  budget_max?: number | null;
  preferred_configuration?: string | null;
  source?: string | null;
  value_paise?: number | null;
}

/** POST /customers/{contactId}/opportunities — idempotent per lead. */
export function openOpportunity(
  contactId: string,
  payload: OpportunityCreatePayload,
): Promise<Opportunity> {
  return bearerRequest<Opportunity>(
    `/customers/${id(contactId)}/opportunities`,
    SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function fetchCustomer(contactId: string): Promise<Customer360Response> {
  return bearerRequest<Customer360Response>(`/customers/${id(contactId)}`, SESSION);
}

export function fetchCustomerTimeline(contactId: string): Promise<Customer360Response> {
  return bearerRequest<Customer360Response>(`/customers/${id(contactId)}/timeline`, SESSION);
}

export function fetchDuplicates(contactId: string): Promise<DuplicateSuggestionsResponse> {
  return bearerRequest<DuplicateSuggestionsResponse>(`/customers/${id(contactId)}/duplicates`, SESSION);
}

export function mergeCustomer(contactId: string, mergedId: string, reason: string): Promise<MergeResponse> {
  return bearerRequest<MergeResponse>(`/customers/${id(contactId)}/merge`, SESSION, {
    method: "POST",
    body: JSON.stringify({ merged_id: mergedId, reason }),
  });
}

export function revertCustomerMerge(mergeId: string): Promise<MergeResponse> {
  return bearerRequest<MergeResponse>(`/customers/merges/${id(mergeId)}/revert`, SESSION, { method: "POST" });
}

export function fetchOpportunities(page = 1, pageSize = 100): Promise<OpportunityListResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return bearerRequest<OpportunityListResponse>(`/opportunities?${params}`, SESSION);
}

export function updateOpportunity(opportunityId: string, payload: OpportunityUpdatePayload): Promise<Opportunity> {
  return bearerRequest<Opportunity>(`/opportunities/${id(opportunityId)}`, SESSION, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
