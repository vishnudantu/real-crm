import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, LoaderCircle, X } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import {
  saleDangerButton,
  saleInputClasses,
  saleLabelClasses,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { documentKeys, voidDocument } from "./documentsApi";
import type { DocumentItem } from "./documentsModel";

interface VoidDocumentDialogProps {
  document: DocumentItem;
  onClose: () => void;
  onVoided: (message: string) => Promise<void> | void;
}

const MAX_REASON_LENGTH = 2000;

/** Admin-only confirmation dialog recording the mandatory void reason. */
export function VoidDocumentDialog({
  document,
  onClose,
  onVoided,
}: VoidDocumentDialogProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (trimmedReason: string) =>
      voidDocument(document.id, trimmedReason),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: documentKeys.all });
      await onVoided(`${document.document_number} voided. Downloads are now blocked.`);
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "Failed to void the document."));
    },
  });

  const trimmedReason = reason.trim();
  const canSubmit = trimmedReason.length > 0 && !mutation.isPending;

  const handleSubmit = () => {
    if (!trimmedReason) {
      setError("A reason is required to void a document.");
      return;
    }
    setError(null);
    mutation.mutate(trimmedReason);
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
        aria-label={`Void ${document.document_number}`}
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Void {document.document_number}
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              The stored PDF is kept for audit, but downloads return 410 once voided.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close void dialog"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit();
          }}
          className="p-5"
        >
          {error && (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {error}
            </p>
          )}

          <label htmlFor="void-reason" className={saleLabelClasses}>
            Reason for voiding <span className="text-rose-500">*</span>
          </label>
          <textarea
            id="void-reason"
            rows={4}
            maxLength={MAX_REASON_LENGTH}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="e.g. Issued against the wrong installment; superseded by a corrected demand letter."
            className={`${saleInputClasses} resize-y`}
          />
          <p className="mt-1 text-[10.5px] text-charcoal/50">
            Recorded permanently on the document proof.
          </p>

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
              disabled={!canSubmit}
              className={saleDangerButton}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <Ban aria-hidden="true" className="size-3.5" />
              )}
              <span>{mutation.isPending ? "Voiding…" : "Void document"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
