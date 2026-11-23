import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, PlusCircle, X } from "lucide-react";
import type { UserItem } from "../admin/adminModel";
import {
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { approvalKeys, createApprovalRequest } from "./approvalsApi";
import type { ApprovalCreateFormErrors, ApprovalCreateFormState } from "./approvalsModel";
import {
  APPROVAL_REFERENCE_TYPES,
  APPROVAL_TYPE_PRESETS,
  MAX_APPROVAL_REASON_LENGTH,
  buildApprovalCreatePayload,
  emptyApprovalCreateForm,
  validateApprovalCreateForm,
} from "./approvalsModel";

interface CreateApprovalRequestModalProps {
  admins: readonly UserItem[];
  onClose: () => void;
  onCreated: (message: string) => void;
}

const CUSTOM_TYPE_OPTION = "__custom__";

/**
 * Staff form for POST /approvals/requests. Wired presets (site-visit car,
 * unit discount, demand letter) set the request/reference pair so the backend
 * side effects apply; a custom type stays audit-only. Optional approver must
 * be an active ADMIN — the picker is fed from the users API.
 */
export function CreateApprovalRequestModal({
  admins,
  onClose,
  onCreated,
}: CreateApprovalRequestModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ApprovalCreateFormState>(emptyApprovalCreateForm);
  const [flowChoice, setFlowChoice] = useState("");
  const [errors, setErrors] = useState<ApprovalCreateFormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (state: ApprovalCreateFormState) =>
      createApprovalRequest(buildApprovalCreatePayload(state)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: approvalKeys.all });
      onCreated("Approval request created and is now pending.");
    },
    onError: (mutationError: unknown) => {
      setSubmitError(errorMessage(mutationError, "The request could not be created."));
    },
  });

  const setField = <Key extends keyof ApprovalCreateFormState>(
    key: Key,
    value: ApprovalCreateFormState[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined, amount: undefined }));
  };

  const applyFlowChoice = (choice: string) => {
    setFlowChoice(choice);
    if (choice === CUSTOM_TYPE_OPTION) {
      setForm((current) => ({ ...current, requestType: "" }));
    } else {
      const preset = APPROVAL_TYPE_PRESETS.find((entry) => entry.requestType === choice);
      setForm((current) => ({
        ...current,
        requestType: choice,
        ...(preset ? { referenceType: preset.referenceType } : {}),
      }));
    }
    setErrors({});
  };

  const selectedPreset = APPROVAL_TYPE_PRESETS.find(
    (entry) => entry.requestType === form.requestType,
  );
  const isCustomType = flowChoice === CUSTOM_TYPE_OPTION;
  const requiresAmount = selectedPreset?.requestType === "DISCOUNT";

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    const validationErrors = validateApprovalCreateForm(form);
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
        aria-label="Create approval request"
        className="max-h-[90svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              New approval request
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Opens a pending request for a manager to decide. Nothing changes until then.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close create dialog"
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
            <label htmlFor="approval-request-type" className={saleLabelClasses}>
              Request type <span className="text-rose-500">*</span>
            </label>
            <select
              id="approval-request-type"
              value={flowChoice}
              onChange={(event) => applyFlowChoice(event.target.value)}
              className={`${saleInputClasses} mt-1`}
            >
              <option value="">Choose a flow…</option>
              {APPROVAL_TYPE_PRESETS.map((preset) => (
                <option key={preset.requestType} value={preset.requestType}>
                  {preset.label} ({preset.requestType})
                </option>
              ))}
              <option value={CUSTOM_TYPE_OPTION}>Other (custom type)…</option>
            </select>
            {isCustomType && (
              <>
                <label htmlFor="approval-custom-type" className={`${saleLabelClasses} mt-3`}>
                  Custom request type <span className="text-rose-500">*</span>
                </label>
                <input
                  id="approval-custom-type"
                  type="text"
                  maxLength={48}
                  value={form.requestType}
                  onChange={(event) => setField("requestType", event.target.value.toUpperCase())}
                  placeholder="e.g. PAYMENT_PLAN_CHANGE"
                  className={`${saleInputClasses} mt-1 font-mono`}
                />
                {errors.requestType && <FieldError message={errors.requestType} />}
              </>
            )}
            {!isCustomType && (
              <p className="mt-1 text-[10.5px] text-charcoal/50">
                These flows update their booking, unit or document automatically once decided.
              </p>
            )}
          </div>

          {isCustomType && form.requestType.trim() && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-[11px] text-amber-800">
              Custom type &ldquo;{form.requestType.trim()}&rdquo; is recorded as an audit request only.
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="approval-reference-type" className={saleLabelClasses}>
                Refers to <span className="text-rose-500">*</span>
              </label>
              <select
                id="approval-reference-type"
                value={form.referenceType}
                onChange={(event) => setField("referenceType", event.target.value)}
                className={`${saleInputClasses} mt-1`}
              >
                {APPROVAL_REFERENCE_TYPES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
              {errors.referenceType && <FieldError message={errors.referenceType} />}
            </div>
            <div>
              <label htmlFor="approval-approver" className={saleLabelClasses}>
                Preferred approver <span className="font-normal text-charcoal/45">(optional)</span>
              </label>
              <select
                id="approval-approver"
                value={form.approverId}
                onChange={(event) => setField("approverId", event.target.value)}
                className={`${saleInputClasses} mt-1`}
              >
                <option value="">Any administrator</option>
                {admins.map((admin) => (
                  <option key={admin.id} value={admin.id}>
                    {admin.full_name} · {admin.email}
                  </option>
                ))}
              </select>
              {errors.approverId && <FieldError message={errors.approverId} />}
            </div>
          </div>

          <div>
            <label htmlFor="approval-reference-id" className={saleLabelClasses}>
              {form.referenceType === "unit"
                ? "Unit ID"
                : form.referenceType === "document"
                  ? "Document ID"
                  : "Booking ID"}{" "}
              <span className="text-rose-500">*</span>
            </label>
            <input
              id="approval-reference-id"
              type="text"
              maxLength={36}
              value={form.referenceId}
              onChange={(event) => setField("referenceId", event.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              className={`${saleInputClasses} mt-1 font-mono`}
            />
            {errors.referenceId ? (
              <FieldError message={errors.referenceId} />
            ) : (
              <p className="mt-1 text-[10.5px] text-charcoal/50">
                Copy this id from the booking, inventory or documents page.
              </p>
            )}
          </div>

          {flowChoice !== "" && (
            <div>
              <label htmlFor="approval-amount" className={saleLabelClasses}>
                Amount (₹){" "}
                {requiresAmount && <span className="text-rose-500">*</span>}
              </label>
              <input
                id="approval-amount"
                type="text"
                inputMode="decimal"
                maxLength={15}
                value={form.amountRupees}
                onChange={(event) => setField("amountRupees", event.target.value)}
                placeholder={requiresAmount ? "Discount amount, e.g. 250000" : "Optional"}
                className={`${saleInputClasses} mt-1`}
              />
              {errors.amountRupees && <FieldError message={errors.amountRupees} />}
              {requiresAmount && !errors.amountRupees && (
                <p className="mt-1 text-[10.5px] text-charcoal/50">
                  A discount approval must carry a positive amount.
                </p>
              )}
            </div>
          )}

          <div>
            <label htmlFor="approval-reason" className={saleLabelClasses}>
              Reason <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="approval-reason"
              rows={4}
              maxLength={MAX_APPROVAL_REASON_LENGTH}
              value={form.reason}
              onChange={(event) => setField("reason", event.target.value)}
              placeholder="What is being approved and why it is needed."
              className={`${saleInputClasses} mt-1 resize-y`}
            />
            {errors.reason && <FieldError message={errors.reason} />}
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
                <PlusCircle aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Creating…" : "Create request"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FieldError({ message }: { message: string }) {
  return (
    <p role="alert" className="mt-1 text-[11px] font-medium text-rose-700">
      {message}
    </p>
  );
}
