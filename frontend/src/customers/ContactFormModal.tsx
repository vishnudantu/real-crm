import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, UserPlus, X } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { createContact, customerKeys, updateContact } from "./customersApi";
import type { Contact, ContactCreateFormState, ContactFormErrors } from "./customersModel";
import { buildContactCreatePayload, validateContactCreateForm } from "./customersModel";

const EMPTY_FORM: ContactCreateFormState = {
  displayName: "",
  email: "",
  phone: "",
  primaryLanguage: "en",
  notes: "",
};

const inputClass = "mt-1 block w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-sm text-charcoal placeholder:text-charcoal/40 focus:border-forest focus:ring-4 focus:ring-forest/10 focus:outline-hidden";
const labelClass = "block text-xs font-semibold text-charcoal/75";

interface CreateMode {
  mode: "create";
  contact?: undefined;
  onCreated: (contact: Contact, created: boolean) => void;
}

interface EditMode {
  mode: "edit";
  contact: Contact;
  onSaved: (contact: Contact) => void;
}

type ContactFormModalProps = (CreateMode | EditMode) & {
  onClose: () => void;
  initialValues?: Partial<ContactCreateFormState>;
};

/**
 * Add/edit console contact form.
 * Create → POST /customers/contacts (idempotent: 200 means identity existed).
 * Edit → PATCH /customers/contacts/{id} (display name / language / notes only;
 * identity methods are managed through merges, so email/phone stay read-only).
 */
export function ContactFormModal(props: ContactFormModalProps) {
  const { onClose } = props;
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const isEdit = props.mode === "edit";
  const [form, setForm] = useState<ContactCreateFormState>({
    ...(isEdit
      ? {
          displayName: props.contact.display_name,
          email: "",
          phone: "",
          primaryLanguage: props.contact.primary_language,
          notes: props.contact.notes ?? "",
        }
      : EMPTY_FORM),
    ...(props.initialValues ?? {}),
  });
  const [errors, setErrors] = useState<ContactFormErrors>({});
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (draft: ContactCreateFormState) =>
      createContact(buildContactCreatePayload(draft)),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: customerKeys.all });
      if (props.mode !== "create") return;
      if (!result.created) {
        setNotice("This contact already exists — opened the matching customer.");
      }
      props.onCreated(result.contact, result.created);
      if (result.created) onClose();
    },
    onError: (error: unknown) => setMutationError(errorMessage(error, "The contact could not be created.")),
  });
  const editMutation = useMutation({
    mutationFn: (payload: { contactId: string; draft: ContactCreateFormState }) =>
      updateContact(payload.contactId, {
        display_name: payload.draft.displayName.trim(),
        primary_language: payload.draft.primaryLanguage.trim().toLowerCase(),
        notes: payload.draft.notes.trim() || null,
      }),
    onSuccess: async (contact) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: customerKeys.all }),
        queryClient.invalidateQueries({ queryKey: customerKeys.detail(contact.id) }),
      ]);
      if (props.mode !== "edit") return;
      props.onSaved(contact);
      onClose();
    },
    onError: (error: unknown) => setMutationError(errorMessage(error, "The contact could not be updated.")),
  });

  const pending = createMutation.isPending || editMutation.isPending;

  const submit = () => {
    setMutationError(null);
    if (props.mode === "edit") {
      const editErrors = validateContactCreateForm({
        ...form,
        email: "existing@example.invalid",
        phone: "",
      });
      delete editErrors.email;
      delete editErrors.phone;
      setErrors(editErrors);
      if (Object.keys(editErrors).length === 0) {
        editMutation.mutate({ contactId: props.contact.id, draft: form });
      }
      return;
    }
    const validation = validateContactCreateForm(form);
    setErrors(validation);
    if (Object.keys(validation).length === 0) createMutation.mutate(form);
  };

  const setField = (key: keyof ContactCreateFormState, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs" onClick={pending ? undefined : onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="contact-form-title"
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 id="contact-form-title" className="text-base font-semibold text-charcoal">
              {isEdit ? "Edit customer" : "Add customer"}
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              {isEdit
                ? "Contact email and phone are identity anchors — change them via duplicate merge, not here."
                : "Email or phone is required. Re-submitting a known identity opens the existing customer instead of duplicating it."}
            </p>
          </div>
          <button type="button" onClick={onClose} disabled={pending} aria-label="Close contact form" className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal disabled:opacity-50">
            <X aria-hidden="true" className="size-4" />
          </button>
        </header>
        <form
          noValidate
          className="space-y-4 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {mutationError && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">{mutationError}</p>}
          {notice && <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800">{notice}</p>}
          <label className={labelClass}>
            Full name <span className="text-rose-500">*</span>
            <input required minLength={2} maxLength={255} value={form.displayName} onChange={(event) => setField("displayName", event.target.value)} placeholder="e.g. Asha Rao" className={inputClass} />
            {errors.displayName && <span className="mt-1 block text-[11px] text-rose-600">{errors.displayName}</span>}
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={labelClass}>
              Email
              {isEdit ? (
                <input disabled value="Managed via merges" className={`${inputClass} disabled:bg-charcoal/5 disabled:text-charcoal/45`} aria-describedby="email-edit-help" />
              ) : (
                <input type="email" maxLength={255} value={form.email} onChange={(event) => setField("email", event.target.value)} placeholder="name@example.com" className={inputClass} />
              )}
              {errors.email && <span className="mt-1 block text-[11px] text-rose-600">{errors.email}</span>}
            </label>
            <label className={labelClass}>
              Phone
              {isEdit ? (
                <input disabled value="Managed via merges" className={`${inputClass} disabled:bg-charcoal/5 disabled:text-charcoal/45`} aria-describedby="phone-edit-help" />
              ) : (
                <input type="tel" maxLength={32} value={form.phone} onChange={(event) => setField("phone", event.target.value)} placeholder="+91 98765 43210" className={inputClass} />
              )}
              {errors.phone && <span className="mt-1 block text-[11px] text-rose-600">{errors.phone}</span>}
            </label>
          </div>
          {isEdit && (
            <p id="email-edit-help" className="sr-only">Email and phone methods are edited through the duplicate-merge flow only.</p>
          )}
          {!isEdit && (errors.email && errors.phone) && (
            <p className="text-[11px] text-charcoal/55">At least one of email or phone is required.</p>
          )}
          <div className="grid gap-4 sm:grid-cols-[160px_minmax(0,1fr)]">
            <label className={labelClass}>
              Primary language
              <input required minLength={2} maxLength={8} value={form.primaryLanguage} onChange={(event) => setField("primaryLanguage", event.target.value)} placeholder="en" className={inputClass} />
              {errors.primaryLanguage && <span className="mt-1 block text-[11px] text-rose-600">{errors.primaryLanguage}</span>}
            </label>
            <label className={labelClass}>
              Notes
              <textarea rows={3} maxLength={5000} value={form.notes} onChange={(event) => setField("notes", event.target.value)} placeholder="Preference, context, family buyers…" className={`${inputClass} resize-y`} />
              {errors.notes && <span className="mt-1 block text-[11px] text-rose-600">{errors.notes}</span>}
            </label>
          </div>
          <footer className="flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button type="button" onClick={onClose} disabled={pending} className="inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-[11px] font-semibold text-charcoal/75 hover:bg-charcoal/5 disabled:opacity-50">
              Cancel
            </button>
            <button type="submit" disabled={pending} className="inline-flex min-h-9 items-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-[11px] font-semibold text-white shadow-xs hover:bg-forest-deep disabled:opacity-55">
              {pending ? <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" /> : <UserPlus aria-hidden="true" className="size-3.5" />}
              {isEdit ? "Save changes" : "Create customer"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
