import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  CheckCircle2,
  Inbox,
  LoaderCircle,
  X,
  XCircle,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import {
  formatDateTime,
  formatInr,
  saleCardClasses,
  saleDangerButton,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { approvalKeys, cancelApprovalRequest } from "./approvalsApi";
import type { ApprovalRequestItem } from "./approvalsModel";
import { canUserCancel, canUserDecide, shortId } from "./approvalsModel";
import { ApprovalStatusChip } from "./ApprovalsUi";
import { ApprovalDecisionModal } from "./ApprovalDecisionModal";

interface ApprovalDetailDrawerProps {
  request: ApprovalRequestItem;
  currentUserId: string;
  isAdmin: boolean;
  onClose: () => void;
  onMessage: (message: string) => void;
}

/** Side drawer with the full request, its decision trail and staff actions. */
export function ApprovalDetailDrawer({
  request,
  currentUserId,
  isAdmin,
  onClose,
  onMessage,
}: ApprovalDetailDrawerProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<"APPROVED" | "REJECTED" | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const cancelMutation = useMutation({
    mutationFn: () => cancelApprovalRequest(request.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: approvalKeys.all });
      onMessage("Approval request cancelled.");
      onClose();
    },
    onError: (error: unknown) => {
      setCancelError(errorMessage(error, "The request could not be cancelled."));
      void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
    },
  });

  const decidable = canUserDecide(request, currentUserId);
  const selfRaised = request.requested_by_id === currentUserId;
  const cancellable = canUserCancel(request, currentUserId, isAdmin);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-stretch justify-end bg-charcoal/45 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Approval request ${request.request_type}`}
        className="flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight text-charcoal">
                {request.request_type}
              </h2>
              <ApprovalStatusChip status={request.status} />
            </div>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Opened {formatDateTime(request.created_at)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close approval details"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <section className={`${saleCardClasses} p-4`}>
            <h3 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
              Reference
            </h3>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
              <DetailRow label="Reference type" value={request.reference_type} />
              <DetailRow label="Reference id" value={shortId(request.reference_id)} mono title={request.reference_id} />
              {request.amount_paise !== null && (
                <DetailRow label="Amount" value={formatInr(request.amount_paise)} />
              )}
              <DetailRow label="Requested by" value={shortId(request.requested_by_id)} mono title={request.requested_by_id ?? undefined} />
              <DetailRow label="Approver" value={shortId(request.approver_id)} mono title={request.approver_id ?? undefined} />
            </dl>
          </section>

          <section className={`${saleCardClasses} p-4`}>
            <h3 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
              Reason
            </h3>
            <p className="mt-2 text-xs leading-6 whitespace-pre-wrap text-charcoal/80">
              {request.reason}
            </p>
          </section>

          {request.status !== "PENDING" && (
            <section className={`${saleCardClasses} p-4`}>
              <h3 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
                Outcome
              </h3>
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
                <DetailRow label="Decided at" value={formatDateTime(request.decided_at)} />
                <DetailRow label="Decided by" value={shortId(request.approver_id)} mono title={request.approver_id ?? undefined} />
              </dl>
              {request.decision_note && (
                <p className="mt-3 rounded-xl border border-charcoal/10 bg-white px-3.5 py-2.5 text-xs leading-5 whitespace-pre-wrap text-charcoal/75">
                  {request.decision_note}
                </p>
              )}
            </section>
          )}

          {request.status === "PENDING" && selfRaised && !decidable && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-[11px] text-amber-800">
              You raised this request — a different administrator must decide it.
            </p>
          )}

          {cancelError && (
            <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
              {cancelError}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2.5 border-t border-charcoal/10 px-5 py-4">
          {request.status === "PENDING" ? (
            <>
              {cancellable && (
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                  className={saleSecondaryButton}
                >
                  {cancelMutation.isPending ? (
                    <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
                  ) : (
                    <Ban aria-hidden="true" className="size-3.5" />
                  )}
                  <span>Cancel request</span>
                </button>
              )}
              {decidable && isAdmin && (
                <>
                  <button
                    type="button"
                    onClick={() => setDecision("REJECTED")}
                    className={saleDangerButton}
                  >
                    <XCircle aria-hidden="true" className="size-3.5" />
                    <span>Reject</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDecision("APPROVED")}
                    className={salePrimaryButton}
                  >
                    <CheckCircle2 aria-hidden="true" className="size-3.5" />
                    <span>Approve</span>
                  </button>
                </>
              )}
              {!decidable && !cancellable && (
                <span className="inline-flex items-center gap-1.5 text-[11px] text-charcoal/50">
                  <Inbox aria-hidden="true" className="size-3.5" />
                  No action available to you on this request.
                </span>
              )}
            </>
          ) : (
            <button type="button" onClick={onClose} className={saleSecondaryButton}>
              Close
            </button>
          )}
        </div>
      </div>

      {decision && (
        <ApprovalDecisionModal
          request={request}
          decision={decision}
          onClose={() => setDecision(null)}
          onDecided={(message) => {
            setDecision(null);
            onClose();
            onMessage(message);
          }}
        />
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  mono = false,
  title,
}: {
  label: string;
  value: string;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div>
      <dt className="text-[10px] font-semibold tracking-wider text-charcoal/45 uppercase">
        {label}
      </dt>
      <dd
        title={title}
        className={`mt-0.5 text-charcoal/80 ${mono ? "font-mono text-[11px]" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
