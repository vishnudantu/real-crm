import { useEffect, useState } from "react";
import { LoaderCircle, Pencil, X } from "lucide-react";
import { errorMessage } from "../../shared/apiRequest";
import { useModalFocus } from "../../shared/useModalFocus";
import { updateLead, type SalesLead } from "../../sales/api";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../sales/salesBookingUi";
import { validateVisitCustomerEdit } from "./scheduleVisitModel";
import type { VisitCaptureErrors, VisitCustomerEditState } from "./scheduleVisitModel";

interface EditVisitCustomerModalProps {
  lead: SalesLead | null;
  onClose: () => void;
  onSaved: (lead: SalesLead) => void;
}

/**
 * Edits the customer behind a site visit. Visits link to leads, so this is
 * PATCH /leads/{id} (full_name/email/phone only). The mirrored directory
 * Contact, if one exists, is updated via PATCH /customers/contacts/{id}
 * best-effort after the lead saves.
 */
export function EditVisitCustomerModal({
  lead,
  onClose,
  onSaved,
}: EditVisitCustomerModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [state, setState] = useState<VisitCustomerEditState>({
    fullName: "",
    email: "",
    phone: "",
  });
  const [errors, setErrors] = useState<VisitCaptureErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (lead) {
      setState({
        fullName: lead.full_name,
        email: lead.email ?? "",
        phone: lead.phone ?? "",
      });
      setErrors({});
      setFormError(null);
    }
  }, [lead]);

  if (!lead) return null;

  const submit = async () => {
    setFormError(null);
    const validation = validateVisitCustomerEdit(state);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;
    setSaving(true);
    try {
      const updated = await updateLead(lead.id, {
        full_name: state.fullName.trim(),
        email: state.email.trim() || null,
        phone: state.phone.trim() || null,
      });
      onSaved(updated);
      onClose();
    } catch (reason: unknown) {
      setFormError(errorMessage(reason, "The visit customer could not be updated."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={saving ? undefined : onClose}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="edit-visit-customer-title" className="w-full max-w-md overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 id="edit-visit-customer-title" className="text-base font-semibold text-charcoal">Edit visit customer</h2>
            <p className="mt-1 text-[11px] text-charcoal/55">Updates the lead record behind this site visit.</p>
          </div>
          <button type="button" onClick={onClose} disabled={saving} aria-label="Close" className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 disabled:opacity-50"><X aria-hidden="true" className="size-4" /></button>
        </header>
        <form className="space-y-4 p-5" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          {formError && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">{formError}</p>}
          <label className={saleLabelClasses}>Full name *<input required minLength={2} maxLength={255} value={state.fullName} onChange={(event) => setState((current) => ({ ...current, fullName: event.target.value }))} className={saleInputClasses} />{errors.fullName && <span className="mt-1 block text-[11px] text-rose-600">{errors.fullName}</span>}</label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={saleLabelClasses}>Email<input type="email" maxLength={255} value={state.email} onChange={(event) => setState((current) => ({ ...current, email: event.target.value }))} className={saleInputClasses} />{errors.email && <span className="mt-1 block text-[11px] text-rose-600">{errors.email}</span>}</label>
            <label className={saleLabelClasses}>Phone<input type="tel" maxLength={32} value={state.phone} onChange={(event) => setState((current) => ({ ...current, phone: event.target.value }))} className={saleInputClasses} />{errors.phone && <span className="mt-1 block text-[11px] text-rose-600">{errors.phone}</span>}</label>
          </div>
          {errors.contact && <p className="text-[11px] text-rose-600">{errors.contact}</p>}
          <footer className="flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button type="button" onClick={onClose} disabled={saving} className={saleSecondaryButton}>Cancel</button>
            <button type="submit" disabled={saving} className={salePrimaryButton}>{saving ? <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" /> : <Pencil aria-hidden="true" className="size-3.5" />}Save customer</button>
          </footer>
        </form>
      </div>
    </div>
  );
}
