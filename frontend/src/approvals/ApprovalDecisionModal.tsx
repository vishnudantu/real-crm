import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, X, XCircle } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import {
  saleDangerButton,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { approvalKeys, decideApprovalRequest } from "./approvalsApi";
import type { ApprovalRequestItem } from "./approvalsModel";
import { MAX_APPROVAL_NOTE_LENGTH } from "./approvalsModel";

interface ApprovalDecisionModalProps {
  request: ApprovalRequestItem;
  decision: "APPROVED" | "REJECTED";
  onClose: () => void;
  onDecided: (message: string) => void;
}

/**
 * Manager confirmation for an APPROVED/REJECTED decision. The note is optional
 * (backend min_length=1 when present, max 2000). Self-approval and
 * non-pending races are blocked server-side; their 409/400/403 messages are
 * surfaced inline and the list is refreshed so the row shows its real state.
 */
export function ApprovalDecisionModal({
  request,
  decision,
  onClose,
  onDecided,
}: ApprovalDecisionModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const approving = decision === "APPROVED";
  const trimmedNote = note.trim();

  const mutation = useMutation({
    mutationFn: () =>
      decideApprovalRequest(request.id, {
        decision,
        ...(trimmedNote ? { note: trimmedNote } : {}),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: approvalKeys.all });
      onDecided(
        `${request.request_type} request ${approving ? "approved" : "rejected"}.`,
      );
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "The decision could not be recorded."));
      // A stale PENDING row (already decided elsewhere) should re-read itself.
      void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
    },
  });

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${approving ? "Approve" : "Reject"} ${request.request_type} request`}
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              {approving ? "Approve request" : "Reject request"}
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              {request.request_type} · {request.reference_type}{" "}
              {request.reference_id.slice(0, 8)}…
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close decision dialog"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (!mutation.isPending) mutation.mutate();
          }}
          className="p-5"
        >
          <p className="rounded-xl border border-charcoal/10 bg-white px-3.5 py-3 text-xs leading-5 text-charcoal/75">
            <span className="font-semibold text-charcoal">Reason given: </span>
            {request.reason}
          </p>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {error}
            </p>
          )}

          <label htmlFor="approval-decision-note" className={`${saleLabelClasses} mt-4`}>
            Decision note <span className="font-normal text-charcoal/45">(optional)</span>
          </label>
          <textarea
            id="approval-decision-note"
            rows={3}
            maxLength={MAX_APPROVAL_NOTE_LENGTH}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={
              approving
                ? "Context for the requester, recorded with the approval."
                : "Why this is being rejected — the requester will see it."
            }
            className={`${saleInputClasses} resize-y`}
          />

          <div className="mt-5 flex items-center justify-end gap-3 border-t border-charcoal/10 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={mutation.isPending}
              className={saleSecondaryButton}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className={approving ? salePrimaryButton : saleDangerButton}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : approving ? (
                <CheckCircle2 aria-hidden="true" className="size-3.5" />
              ) : (
                <XCircle aria-hidden="true" className="size-3.5" />
              )}
              <span>
                {mutation.isPending
                  ? "Recording…"
                  : approving
                    ? "Approve"
                    : "Reject"}
              </span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
