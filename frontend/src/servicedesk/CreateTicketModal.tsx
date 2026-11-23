import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, TicketPlus, X } from "lucide-react";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { createTicket, ticketKeys } from "./serviceDeskApi";
import type { TicketCreateFormErrors, TicketCreateFormState } from "./serviceDeskModel";
import {
  MAX_TICKET_DESCRIPTION_LENGTH,
  MAX_TICKET_SUBJECT_LENGTH,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  emptyTicketCreateForm,
  validateTicketCreateForm,
} from "./serviceDeskModel";

interface CreateTicketModalProps {
  onClose: () => void;
  onCreated: (message: string) => void;
}

/** Staff form for POST /service-desk/tickets. Priority is chosen here only;
 * there is no priority-update endpoint, so it cannot be changed later. */
export function CreateTicketModal({ onClose, onCreated }: CreateTicketModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TicketCreateFormState>(emptyTicketCreateForm);
  const [errors, setErrors] = useState<TicketCreateFormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (state: TicketCreateFormState) =>
      createTicket({
        subject: state.subject.trim(),
        description: state.description.trim(),
        category: state.category,
        priority: state.priority,
      }),
    onSuccess: async (ticket) => {
      await queryClient.invalidateQueries({ queryKey: ticketKeys.all });
      onCreated(`Ticket ${ticket.ticket_number} opened.`);
    },
    onError: (error: unknown) => {
      setSubmitError(errorMessage(error, "The ticket could not be created."));
    },
  });

  const setField = <Key extends keyof TicketCreateFormState>(
    key: Key,
    value: TicketCreateFormState[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    const validationErrors = validateTicketCreateForm(form);
    setErrors(validationErrors);
    if (Object.values(validationErrors).some((message) => Boolean(message))) return;
    mutation.mutate(form);
  };

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Create support ticket"
        className="max-h-[90svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              New support ticket
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              A TCK number and SLA deadline are assigned from the priority when saved.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close create ticket dialog"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          {submitError && (
            <p
              role="alert"
              className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {submitError}
            </p>
          )}

          <div>
            <label htmlFor="ticket-subject" className={saleLabelClasses}>
              Subject <span className="text-rose-500">*</span>
            </label>
            <input
              id="ticket-subject"
              type="text"
              maxLength={MAX_TICKET_SUBJECT_LENGTH}
              value={form.subject}
              onChange={(event) => setField("subject", event.target.value)}
              placeholder="Short summary of the customer issue"
              className={`${saleInputClasses} mt-1`}
            />
            {errors.subject && (
              <p role="alert" className="mt-1 text-[11px] font-medium text-rose-700">
                {errors.subject}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="ticket-description" className={saleLabelClasses}>
              Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="ticket-description"
              rows={5}
              maxLength={MAX_TICKET_DESCRIPTION_LENGTH}
              value={form.description}
              onChange={(event) => setField("description", event.target.value)}
              placeholder="What happened, when, and what the customer expects."
              className={`${saleInputClasses} mt-1 resize-y`}
            />
            {errors.description && (
              <p role="alert" className="mt-1 text-[11px] font-medium text-rose-700">
                {errors.description}
              </p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="ticket-category" className={saleLabelClasses}>
                Category
              </label>
              <select
                id="ticket-category"
                value={form.category}
                onChange={(event) =>
                  setField("category", event.target.value as TicketCreateFormState["category"])
                }
                className={`${saleInputClasses} mt-1`}
              >
                {TICKET_CATEGORIES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="ticket-priority" className={saleLabelClasses}>
                Priority
              </label>
              <select
                id="ticket-priority"
                value={form.priority}
                onChange={(event) =>
                  setField("priority", event.target.value as TicketCreateFormState["priority"])
                }
                className={`${saleInputClasses} mt-1`}
              >
                {TICKET_PRIORITIES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10.5px] text-charcoal/50">
                Sets the SLA: 4h / 24h / 72h / 7d. Cannot be changed later.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={mutation.isPending}
              className={saleSecondaryButton}
            >
              Cancel
            </button>
            <button type="submit" disabled={mutation.isPending} className={salePrimaryButton}>
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <TicketPlus aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Creating…" : "Create ticket"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
