import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";
import { errorMessage } from "../shared/apiRequest";
import {
  convertHold,
  createHold,
  extendHold,
  releaseHold,
} from "./inventoryApi";
import type { HoldResponse, Unit } from "./inventoryModel";
import { DEFAULT_HOLD_HOURS, isUuid, paiseToRupeesFormat, rupeesToPaise } from "./inventoryModel";
import {
  inventoryDangerButton,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
  inventorySecondaryButton,
} from "./inventoryUi";

interface DialogShellProps {
  title: string;
  description: string;
  onClose: () => void;
  children: React.ReactNode;
}

function DialogShell({ title, description, onClose, children }: DialogShellProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90svh] w-full max-w-md overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold tracking-tight text-charcoal">{title}</h3>
            <p className="mt-1 text-[11px] leading-relaxed text-charcoal/55">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={`Close ${title}`}
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

interface HoldDialogProps {
  unit: Unit;
  onClose: () => void;
  onSuccess: (hold: HoldResponse, message: string) => void | Promise<void>;
}

export function HoldForBuyerDialog({ unit, onClose, onSuccess }: HoldDialogProps) {
  const [leadId, setLeadId] = useState("");
  const [opportunityRef, setOpportunityRef] = useState("");
  const [hours, setHours] = useState(String(DEFAULT_HOLD_HOURS));
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createHold({
        unit_id: unit.id,
        lead_id: leadId.trim() || null,
        opportunity_ref: opportunityRef.trim() || null,
        hours: Number(hours),
        reason: reason.trim(),
      }),
    onSuccess: (hold) => onSuccess(hold, `Hold placed on ${unit.internal_code}.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to place hold.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!reason.trim()) {
      setFormError("A reason is required for the hold.");
      return;
    }
    const hoursNumber = Number(hours);
    if (!Number.isInteger(hoursNumber) || hoursNumber < 1 || hoursNumber > 720) {
      setFormError("Hold duration must be between 1 and 720 hours.");
      return;
    }
    const lead = leadId.trim();
    if (lead && !isUuid(lead)) {
      setFormError("Lead ID must be a valid UUID, or leave it blank.");
      return;
    }
    setFormError(null);
    mutation.mutate();
  };

  return (
    <DialogShell
      title={`Hold ${unit.internal_code} for buyer`}
      description="Places an exclusive, time-bound hold. The unit moves to On hold until it is released, expires, or converts to a booking."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <div>
          <label htmlFor="hold-lead-id" className={inventoryLabelClasses}>
            Lead ID (UUID, optional)
          </label>
          <input
            id="hold-lead-id"
            value={leadId}
            onChange={(event) => setLeadId(event.target.value)}
            placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6"
            className={`${inventoryInputClasses} font-mono`}
          />
          <p className="mt-1 text-[11px] leading-relaxed text-charcoal/50">
            Paste the lead's UUID from the Leads workspace. A lead is required before this hold
            can convert to a booking — lead search is not yet wired to this dialog.
          </p>
        </div>
        <div>
          <label htmlFor="hold-opportunity-ref" className={inventoryLabelClasses}>
            Opportunity reference (optional)
          </label>
          <input
            id="hold-opportunity-ref"
            value={opportunityRef}
            onChange={(event) => setOpportunityRef(event.target.value)}
            maxLength={128}
            className={inventoryInputClasses}
          />
        </div>
        <div>
          <label htmlFor="hold-hours" className={inventoryLabelClasses}>
            Hold duration (hours)
          </label>
          <input
            id="hold-hours"
            type="number"
            min={1}
            max={720}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
            className={inventoryInputClasses}
          />
        </div>
        <div>
          <label htmlFor="hold-reason" className={inventoryLabelClasses}>
            Reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            id="hold-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="e.g. Buyer token promised by tomorrow"
            className={inventoryInputClasses}
          />
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={inventoryPrimaryButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Placing hold…" : "Place hold"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}

interface ExtendDialogProps {
  hold: HoldResponse;
  unitCode: string;
  onClose: () => void;
  onSuccess: (hold: HoldResponse, message: string) => void | Promise<void>;
}

export function ExtendHoldDialog({ hold, unitCode, onClose, onSuccess }: ExtendDialogProps) {
  const [hours, setHours] = useState("24");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      extendHold(hold.id, { hours: Number(hours), reason: reason.trim() || null }),
    onSuccess: (updated) => onSuccess(updated, `Hold on ${unitCode} extended.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to extend hold.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const hoursNumber = Number(hours);
    if (!Number.isInteger(hoursNumber) || hoursNumber < 1 || hoursNumber > 720) {
      setFormError("Extension must be between 1 and 720 hours.");
      return;
    }
    setFormError(null);
    mutation.mutate();
  };

  return (
    <DialogShell
      title={`Extend hold on ${unitCode}`}
      description={`Extension ${hold.extension_count + 1} of 2. The new duration is added to the current expiry.`}
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <div>
          <label htmlFor="extend-hours" className={inventoryLabelClasses}>
            Extend by (hours)
          </label>
          <input
            id="extend-hours"
            type="number"
            min={1}
            max={720}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
            className={inventoryInputClasses}
          />
        </div>
        <div>
          <label htmlFor="extend-reason" className={inventoryLabelClasses}>
            Reason (optional)
          </label>
          <textarea
            id="extend-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={2}
            maxLength={2000}
            className={inventoryInputClasses}
          />
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={inventoryPrimaryButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Extending…" : "Extend hold"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}

interface ReleaseDialogProps {
  holdId: string;
  unitCode: string;
  onClose: () => void;
  onSuccess: (hold: HoldResponse, message: string) => void | Promise<void>;
}

export function ReleaseHoldDialog({ holdId, unitCode, onClose, onSuccess }: ReleaseDialogProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => releaseHold(holdId, reason.trim()),
    onSuccess: (updated) => onSuccess(updated, `Hold on ${unitCode} released; unit is available again.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to release hold.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!reason.trim()) {
      setFormError("A release reason is required.");
      return;
    }
    setFormError(null);
    mutation.mutate();
  };

  return (
    <DialogShell
      title={`Release hold on ${unitCode}`}
      description="Releases the hold and returns the unit to Available. This is recorded in the status history."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <div>
          <label htmlFor="release-reason" className={inventoryLabelClasses}>
            Release reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            id="release-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="e.g. Buyer withdrew interest"
            className={inventoryInputClasses}
          />
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={inventoryDangerButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Releasing…" : "Release hold"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}

interface ConvertDialogProps {
  hold: HoldResponse;
  unitCode: string;
  onClose: () => void;
  onSuccess: (hold: HoldResponse, message: string) => void | Promise<void>;
}

export function ConvertHoldDialog({ hold, unitCode, onClose, onSuccess }: ConvertDialogProps) {
  const [rupees, setRupees] = useState("");
  const [bookedOn, setBookedOn] = useState(() => new Date().toISOString().split("T")[0]);
  const [formError, setFormError] = useState<string | null>(null);

  const paise = rupeesToPaise(rupees);
  const validPaise = Number.isFinite(paise) && paise > 0;

  const mutation = useMutation({
    mutationFn: () =>
      convertHold(hold.id, { consideration_paise: paise, booked_on: bookedOn || null }),
    onSuccess: (result) =>
      onSuccess(result.hold, `Hold on ${unitCode} converted to booking ${result.booking_id}.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to convert hold to booking.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!validPaise) {
      setFormError("Enter a positive consideration amount in rupees.");
      return;
    }
    if (!hold.lead_id) {
      setFormError("This hold has no lead attached, so it cannot convert to a booking.");
      return;
    }
    setFormError(null);
    mutation.mutate();
  };

  return (
    <DialogShell
      title={`Convert ${unitCode} to booking`}
      description="Creates the sale booking, marks the hold converted, and moves the unit to Booked in one transaction."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        {!hold.lead_id && (
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs leading-relaxed text-amber-800">
            This hold has no lead attached. The backend requires a lead before conversion; attach
            one by releasing and re-holding with a lead ID.
          </p>
        )}
        <div>
          <label htmlFor="convert-consideration" className={inventoryLabelClasses}>
            Consideration (₹ rupees) <span className="text-rose-500">*</span>
          </label>
          <input
            id="convert-consideration"
            inputMode="decimal"
            value={rupees}
            onChange={(event) => setRupees(event.target.value)}
            placeholder="7500000 or 7500000.50"
            className={inventoryInputClasses}
          />
          <p className="mt-1 text-[11px] text-charcoal/55">
            {validPaise ? (
              <>
                {paiseToRupeesFormat(paise)} = <span className="font-mono">{paise.toLocaleString("en-IN")}</span> paise
              </>
            ) : (
              "Amount is sent to the server as integer paise (rounded to the nearest paise)."
            )}
          </p>
        </div>
        <div>
          <label htmlFor="convert-booked-on" className={inventoryLabelClasses}>
            Booked on
          </label>
          <input
            id="convert-booked-on"
            type="date"
            value={bookedOn}
            onChange={(event) => setBookedOn(event.target.value)}
            className={inventoryInputClasses}
          />
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending || !hold.lead_id}
            title={!hold.lead_id ? "A lead is required before conversion" : undefined}
            className={inventoryPrimaryButton}
          >
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Converting…" : "Convert to booking"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
