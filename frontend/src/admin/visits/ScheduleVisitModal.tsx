import { useEffect, useMemo, useState } from "react";
import {
  CalendarPlus,
  LoaderCircle,
  Sparkles,
  UserPlus,
  X,
} from "lucide-react";
import { errorMessage } from "../../shared/apiRequest";
import { useModalFocus } from "../../shared/useModalFocus";
import type { ProjectItem } from "../projectModel";
import { createContact, openOpportunity } from "../../customers/customersApi";
import {
  createBooking,
  createLead,
  fetchAvailableSlots,
  scheduleCustomBooking,
  type AvailableSlot,
  type LeadSource,
  type SalesLead,
} from "../../sales/api";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../sales/salesBookingUi";
import {
  buildVisitLeadPayload,
  INITIAL_VISIT_CAPTURE,
  leadLabel,
  validateVisitCapture,
} from "./scheduleVisitModel";
import type { VisitCaptureErrors, VisitCaptureState } from "./scheduleVisitModel";

const LEAD_SOURCES: readonly { value: LeadSource; label: string }[] = [
  { value: "REFERRAL", label: "Referral" },
  { value: "WEBSITE", label: "Website" },
  { value: "PROPERTY_PORTAL", label: "Property portal" },
  { value: "SOCIAL_MEDIA", label: "Social media" },
  { value: "HOARDING", label: "Hoarding" },
  { value: "OTHER", label: "Other" },
];

interface ScheduleVisitModalProps {
  isOpen: boolean;
  leads: SalesLead[];
  projects: ProjectItem[];
  onClose: () => void;
  onScheduled: (booking: { buyer_name: string }) => void;
  onLeadsChanged: () => void;
}

function toLocalInput(date: Date): string {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Mount-gated wrapper so hooks only run while the modal is open. */
export function ScheduleVisitModal(props: ScheduleVisitModalProps) {
  if (!props.isOpen) return null;
  return <ScheduleVisitModalContent {...props} />;
}

/**
 * Admin site-visit scheduler with customer capture.
 *
 * Backend contract: POST /bookings accepts only slot_id + lead_id + notes and
 * POST /bookings/schedule-custom only lead_id + start/end + notes — bookings
 * link to leads, not contacts, so no contact_id field is invented. "New
 * customer" here creates a Lead (POST /leads), then best-effort attaches the
 * canonical Contact (POST /customers/contacts, idempotent) and a lead-linked
 * Opportunity so the visit is connected to the customer graph.
 */
function ScheduleVisitModalContent({
  leads,
  projects,
  onClose,
  onScheduled,
  onLeadsChanged,
}: ScheduleVisitModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [capture, setCapture] = useState<VisitCaptureState>(INITIAL_VISIT_CAPTURE);
  const [newProjectId, setNewProjectId] = useState("");
  const [errors, setErrors] = useState<VisitCaptureErrors>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [slots, setSlots] = useState<AvailableSlot[]>([]);
  const [slotId, setSlotId] = useState("");
  const [timingMode, setTimingMode] = useState<"slot" | "custom">("slot");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [notes, setNotes] = useState("");

  const selectedLead =
    capture.mode === "existing"
      ? leads.find((lead) => lead.id === capture.leadId) ?? null
      : null;
  const activeProject = useMemo(() => {
    const projectId =
      capture.mode === "existing"
        ? selectedLead?.project_id
        : newProjectId || null;
    return projects.find((item) => item.id === projectId) ?? null;
  }, [capture.mode, newProjectId, projects, selectedLead]);

  useEffect(() => {
    let active = true;
    if (!activeProject) {
      setSlots([]);
      return;
    }
    setBusy("slots");
    fetchAvailableSlots(activeProject.id)
      .then((response) => {
        if (!active) return;
        setSlots(response.items);
        setSlotId(response.items[0]?.id ?? "");
        if (response.items.length === 0) setTimingMode("custom");
      })
      .catch(() => {
        if (active) setTimingMode("custom");
      })
      .finally(() => {
        if (active) setBusy(null);
      });
    return () => {
      active = false;
    };
  }, [activeProject]);

  useEffect(() => {
    if (!start && !end) {
      const tomorrow = new Date(Date.now() + 86_400_000);
      tomorrow.setHours(10, 0, 0, 0);
      setStart(toLocalInput(tomorrow));
      setEnd(toLocalInput(new Date(tomorrow.getTime() + 3_600_000)));
    }
  }, [start, end]);

  const setField = <K extends keyof VisitCaptureState>(
    key: K,
    value: VisitCaptureState[K],
  ) => setCapture((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    setFormError(null);
    const validation = validateVisitCapture(capture);
    if (capture.mode === "new" && !newProjectId) {
      validation.leadId = "Choose the project for this visit.";
    }
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    try {
      let leadId = capture.leadId;
      let createdLead: SalesLead | null = null;
      if (capture.mode === "new") {
        setBusy("lead");
        createdLead = await createLead(
          buildVisitLeadPayload(capture, newProjectId),
        );
        leadId = createdLead.id;
      }
      if (timingMode === "slot") {
        if (!slotId) throw new Error("Select an available slot or switch to custom time.");
        setBusy("booking");
        const booking = await createBooking({
          slot_id: slotId,
          lead_id: leadId,
          notes: notes.trim() || undefined,
        });
        onScheduled(booking);
      } else {
        const startDate = new Date(start);
        const endDate = new Date(end);
        if (startDate.getTime() <= Date.now()) {
          throw new Error("Visit start time must be in the future.");
        }
        if (endDate.getTime() <= startDate.getTime()) {
          throw new Error("End time must be after start time.");
        }
        setBusy("booking");
        const booking = await scheduleCustomBooking({
          lead_id: leadId,
          start_time: startDate.toISOString(),
          end_time: endDate.toISOString(),
          notes: notes.trim() || undefined,
        });
        onScheduled(booking);
      }
      if (createdLead) {
        // Customer-graph link is best-effort and runs after the visit exists.
        setBusy(null);
        void attachCustomerGraph(createdLead)
          .catch(() => undefined)
          .finally(() => onLeadsChanged());
      }
      onLeadsChanged();
      onClose();
    } catch (reason: unknown) {
      setFormError(errorMessage(reason, "The site visit could not be scheduled."));
    } finally {
      setBusy(null);
    }
  };

  const attachCustomerGraph = async (lead: SalesLead) => {
    if (!lead.email && !lead.phone) return;
    const result = await createContact({
      display_name: lead.full_name,
      email: lead.email,
      phone: lead.phone,
      primary_language: "en",
      notes: "Created while scheduling a site visit.",
    });
    await openOpportunity(result.contact.id, {
      project_id: lead.project_id,
      from_lead_id: lead.id,
    }).catch(() => undefined);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={busy ? undefined : onClose}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="schedule-visit-title" className="max-h-[92svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 id="schedule-visit-title" className="text-base font-semibold text-charcoal">Schedule site visit</h2>
            <p className="mt-1 text-[11px] text-charcoal/55">Pick an existing lead customer or capture a new one. Visits link to leads, and new customers are added to the directory automatically.</p>
          </div>
          <button type="button" onClick={onClose} disabled={Boolean(busy)} aria-label="Close schedule dialog" className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 disabled:opacity-50"><X aria-hidden="true" className="size-4" /></button>
        </header>
        <form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          {formError && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">{formError}</p>}
          <fieldset className="rounded-xl border border-charcoal/10 p-3">
            <legend className="px-1 text-[10px] font-semibold uppercase tracking-wider text-charcoal/50">Customer</legend>
            <div className="mb-3 flex rounded-xl border border-charcoal/10 bg-charcoal/5 p-1">
              {(["existing", "new"] as const).map((mode) => (
                <button key={mode} type="button" onClick={() => setField("mode", mode)} className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors ${capture.mode === mode ? "bg-white text-forest shadow-xs" : "text-charcoal/60 hover:text-charcoal"}`}>
                  {mode === "existing" ? "Existing lead" : "New customer"}
                </button>
              ))}
            </div>
            {capture.mode === "existing" ? (
              <label className={saleLabelClasses}>
                Lead customer
                <select className={saleInputClasses} value={capture.leadId} onChange={(event) => setField("leadId", event.target.value)}>
                  <option value="">Select a lead…</option>
                  {leads.map((lead) => (
                    <option key={lead.id} value={lead.id}>
                      {leadLabel(lead, projects.find((item) => item.id === lead.project_id)?.name ?? null)}
                    </option>
                  ))}
                </select>
                {errors.leadId && <span className="mt-1 block text-[11px] text-rose-600">{errors.leadId}</span>}
              </label>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className={saleLabelClasses}>Full name *<input required maxLength={255} value={capture.fullName} onChange={(event) => setField("fullName", event.target.value)} className={saleInputClasses} /></label>
                  <label className={saleLabelClasses}>Project *
                    <select required className={saleInputClasses} value={newProjectId} onChange={(event) => setNewProjectId(event.target.value)}>
                      <option value="">Select a project…</option>
                      {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                </div>
                {errors.fullName && <p className="text-[11px] text-rose-600">{errors.fullName}</p>}
                {errors.leadId && <p className="text-[11px] text-rose-600">{errors.leadId}</p>}
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className={saleLabelClasses}>Email<input type="email" maxLength={255} value={capture.email} onChange={(event) => setField("email", event.target.value)} className={saleInputClasses} /></label>
                  <label className={saleLabelClasses}>Phone<input type="tel" maxLength={32} value={capture.phone} onChange={(event) => setField("phone", event.target.value)} className={saleInputClasses} /></label>
                </div>
                {(errors.contact || errors.email || errors.phone) && <p className="text-[11px] text-rose-600">{errors.contact ?? errors.email ?? errors.phone}</p>}
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className={saleLabelClasses}>Source<select className={saleInputClasses} value={capture.source} onChange={(event) => setField("source", event.target.value as LeadSource)}>{LEAD_SOURCES.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
                  <label className="mt-5 flex items-center gap-2 text-xs font-medium text-charcoal">
                    <input type="checkbox" checked={capture.consentToContact} onChange={(event) => setField("consentToContact", event.target.checked)} className="size-4 rounded border-charcoal/20 accent-forest" />
                    Consent to contact (DPDP)
                  </label>
                </div>
                {errors.consent && <p className="text-[11px] text-rose-600">{errors.consent}</p>}
              </div>
            )}
          </fieldset>
          {activeProject && (
            <div className="rounded-xl border border-charcoal/10 bg-white px-3.5 py-2.5 text-xs text-charcoal/65">
              <span className="font-semibold text-charcoal">{activeProject.name}</span> · {activeProject.location}
              {busy === "slots" && <span className="ml-2 inline-flex items-center gap-1 text-charcoal/45"><LoaderCircle aria-hidden="true" className="size-3 animate-spin" />loading slots…</span>}
            </div>
          )}
          <fieldset className="rounded-xl border border-charcoal/10 p-3">
            <legend className="px-1 text-[10px] font-semibold uppercase tracking-wider text-charcoal/50">Timing</legend>
            <div className="mb-3 flex rounded-xl border border-charcoal/10 bg-charcoal/5 p-1">
              {(["slot", "custom"] as const).map((mode) => (
                <button key={mode} type="button" onClick={() => setTimingMode(mode)} className={`flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors ${timingMode === mode ? "bg-white text-forest shadow-xs" : "text-charcoal/60 hover:text-charcoal"}`}>
                  {mode === "slot" ? `Open slots (${slots.length})` : "Custom time"}
                </button>
              ))}
            </div>
            {timingMode === "slot" ? (
              slots.length === 0 ? (
                <p className="text-xs text-charcoal/55">No open slots for this project. Switch to a custom time — one is created automatically.</p>
              ) : (
                <div className="max-h-40 space-y-2 overflow-y-auto pr-1">
                  {slots.map((slot) => (
                    <button key={slot.id} type="button" onClick={() => setSlotId(slot.id)} className={`flex w-full items-center justify-between rounded-xl border p-3 text-left text-xs transition-colors ${slotId === slot.id ? "border-forest bg-forest/5" : "border-charcoal/10 bg-white hover:border-charcoal/25"}`}>
                      <span className="font-semibold">{new Date(slot.start_time).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} – {new Date(slot.end_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
                      <span className="font-semibold text-forest">{slot.available_capacity} left</span>
                    </button>
                  ))}
                </div>
              )
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={saleLabelClasses}>Start<input required type="datetime-local" value={start} min={toLocalInput(new Date())} onChange={(event) => setStart(event.target.value)} className={saleInputClasses} /></label>
                <label className={saleLabelClasses}>End<input required type="datetime-local" value={end} min={start} onChange={(event) => setEnd(event.target.value)} className={saleInputClasses} /></label>
              </div>
            )}
          </fieldset>
          <label className={saleLabelClasses}>Visit notes<textarea rows={2} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Parking instructions, preferred unit, family buyers…" className={`${saleInputClasses} resize-y`} /></label>
          <footer className="flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button type="button" onClick={onClose} disabled={Boolean(busy)} className={saleSecondaryButton}>Cancel</button>
            <button type="submit" disabled={Boolean(busy)} className={salePrimaryButton}>
              {busy && busy !== "slots" ? <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" /> : capture.mode === "new" ? <UserPlus aria-hidden="true" className="size-3.5" /> : <CalendarPlus aria-hidden="true" className="size-3.5" />}
              {busy === "lead" ? "Creating customer…" : busy === "booking" ? "Booking visit…" : capture.mode === "new" ? "Create & schedule" : "Confirm visit"}
            </button>
          </footer>
          <p className="text-[10.5px] leading-4 text-charcoal/45"><Sparkles aria-hidden="true" className="mr-1 inline size-3" />Custom times create the visit slot automatically. New customers are saved as leads and mirrored into the customer directory with an opportunity for this project.</p>
        </form>
      </div>
    </div>
  );
}
