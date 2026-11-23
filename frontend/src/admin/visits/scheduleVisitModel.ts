import type { LeadSource } from "../../sales/api";
import type { LeadCreatePayload } from "../../sales/api";

/**
 * Site visits (bookings) link to a Lead, not a Contact: the backend
 * BookingCreateRequest accepts only slot_id, lead_id and notes. Capturing a
 * "new customer" on a visit therefore creates a lead (canonical Contact is
 * created best-effort via the idempotent POST /customers/contacts).
 */
export type VisitCustomerMode = "existing" | "new";

export interface VisitCaptureState {
  mode: VisitCustomerMode;
  leadId: string;
  fullName: string;
  email: string;
  phone: string;
  source: LeadSource;
  consentToContact: boolean;
}

export type VisitCaptureErrors = Partial<
  Record<"leadId" | "fullName" | "contact" | "email" | "phone" | "consent", string>
>;

export const INITIAL_VISIT_CAPTURE: VisitCaptureState = {
  mode: "existing",
  leadId: "",
  fullName: "",
  email: "",
  phone: "",
  source: "OTHER",
  consentToContact: true,
};

export function validateVisitCapture(state: VisitCaptureState): VisitCaptureErrors {
  const errors: VisitCaptureErrors = {};
  if (state.mode === "existing") {
    if (!state.leadId) errors.leadId = "Choose the lead this visit belongs to.";
    return errors;
  }
  const name = state.fullName.trim();
  if (name.length < 2) errors.fullName = "Customer name must be at least 2 characters.";
  const email = state.email.trim();
  const phone = state.phone.trim();
  if (!email && !phone) {
    errors.contact = "Capture at least one of email or phone.";
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (phone && !/^\+?[0-9\s().-]{7,32}$/.test(phone)) {
    errors.phone = "Phone may use digits, +, -, spaces, dots and parentheses.";
  }
  if (!state.consentToContact) {
    errors.consent = "Contact consent is required before scheduling a visit (DPDP).";
  }
  return errors;
}

export function buildVisitLeadPayload(
  state: VisitCaptureState,
  projectId: string,
): LeadCreatePayload {
  return {
    full_name: state.fullName.trim(),
    email: state.email.trim() || null,
    phone: state.phone.trim() || null,
    project_id: projectId,
    source: state.source,
    consent_to_contact: state.consentToContact,
  };
}

/** Lead for the selected (existing) customer, if any. */
export interface LeadOption {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  project_id: string;
  opted_out: boolean;
}

export function leadLabel(lead: LeadOption, projectName: string | null): string {
  const contact = lead.email ?? lead.phone ?? "no contact on file";
  const optedOut = lead.opted_out ? " · opted out" : "";
  return `${lead.full_name} (${contact}${optedOut})${projectName ? ` — ${projectName}` : ""}`;
}

export interface VisitCustomerEditState {
  fullName: string;
  email: string;
  phone: string;
}

export function validateVisitCustomerEdit(
  state: VisitCustomerEditState,
): VisitCaptureErrors {
  const errors: VisitCaptureErrors = {};
  if (state.fullName.trim().length < 2) {
    errors.fullName = "Customer name must be at least 2 characters.";
  }
  const email = state.email.trim();
  const phone = state.phone.trim();
  if (!email && !phone) errors.contact = "Keep at least one of email or phone.";
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (phone && !/^\+?[0-9\s().-]{7,32}$/.test(phone)) {
    errors.phone = "Phone may use digits, +, -, spaces, dots and parentheses.";
  }
  return errors;
}
