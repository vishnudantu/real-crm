import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FilePlus2, LoaderCircle } from "lucide-react";
import { errorMessage } from "../../shared/apiRequest";
import {
  documentKeys,
  issueDemandLetter,
  issueReceiptPdf,
} from "../../documents/documentsApi";
import type { DocumentItem } from "../../documents/documentsModel";
import { documentDownloadFilename } from "../../documents/documentsModel";
import { DocumentFeedbackBanner } from "../../documents/DocumentFeedbackBanner";
import { useDocumentDownload } from "../../documents/useDocumentDownload";
import { salePrimaryButton, saleSecondaryButton } from "./salesBookingUi";

/** State shared by both ledger cells: the last issued document + its feedback. */
interface IssuedState {
  document: DocumentItem;
}

function useIssueDocument() {
  const queryClient = useQueryClient();
  const [issued, setIssued] = useState<IssuedState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: documentKeys.all });
  };

  return { issued, setIssued, error, setError, invalidate };
}

interface CellProps {
  /** Ledger rows use this to lift a success message into the page-level toast. */
  onIssued: (message: string) => Promise<void> | void;
}

/**
 * Installment-row action: issue the demand-letter PDF for one installment.
 * The booking ledger's existing "Demand" button only queues messaging; this
 * generates the actual document and offers an authenticated download.
 */
export function IssueDemandLetterCell({
  installmentId,
  outstandingPaise,
  onIssued,
}: CellProps & { installmentId: string; outstandingPaise: number }) {
  const { issued, setIssued, error, setError, invalidate } = useIssueDocument();
  const {
    downloadingId,
    feedback,
    error: downloadError,
    clearFeedback,
    download,
  } = useDocumentDownload();

  const mutation = useMutation({
    mutationFn: () => issueDemandLetter(installmentId),
    onSuccess: async (document) => {
      setIssued({ document });
      await invalidate();
      await onIssued(`Demand letter ${document.document_number} issued.`);
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "Failed to issue the demand letter."));
    },
  });

  const busy = mutation.isPending || downloadingId === issued?.document.id;
  const open = outstandingPaise > 0;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap justify-end gap-1.5">
        <button
          type="button"
          onClick={() => {
            setError(null);
            setIssued(null);
            mutation.mutate();
          }}
          disabled={!open || busy}
          title={
            open
              ? "Generate (or return the already-issued) demand-letter PDF for this installment."
              : "This installment has no outstanding amount."
          }
          className={salePrimaryButton}
          aria-label="Issue demand letter PDF"
        >
          {mutation.isPending ? (
            <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
          ) : (
            <FilePlus2 aria-hidden="true" className="size-3" />
          )}
          <span>{mutation.isPending ? "Issuing…" : "Issue letter"}</span>
        </button>
        {issued && (
          <button
            type="button"
            onClick={() =>
              void download(issued.document.id, issued.document.document_number)
            }
            disabled={downloadingId === issued.document.id}
            className={saleSecondaryButton}
            aria-label={`Download ${issued.document.document_number}`}
          >
            {downloadingId === issued.document.id ? (
              <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
            ) : (
              <Download aria-hidden="true" className="size-3" />
            )}
            <span>Download</span>
          </button>
        )}
      </div>
      {issued && !feedback && (
        <p className="text-right text-[10px] text-charcoal/55">
          {issued.document.document_number} · v{issued.document.template_version}
        </p>
      )}
      {(error || downloadError || feedback) && (
        <DocumentFeedbackBanner
          feedback={feedback}
          error={error ?? downloadError}
          onDismiss={() => {
            setError(null);
            clearFeedback();
          }}
        />
      )}
    </div>
  );
}

/**
 * Receipt-row action: generate the receipt PDF on demand, then download it.
 * Issuance is idempotent per template version, so repeat clicks are safe.
 */
export function ReceiptDocumentCell({ receiptId, onIssued }: CellProps & { receiptId: string }) {
  const { issued, setIssued, error, setError, invalidate } = useIssueDocument();
  const {
    downloadingId,
    feedback,
    error: downloadError,
    clearFeedback,
    download,
  } = useDocumentDownload();

  const mutation = useMutation({
    mutationFn: () => issueReceiptPdf(receiptId),
    onSuccess: async (document) => {
      setIssued({ document });
      await invalidate();
      await onIssued(`Receipt PDF ${document.document_number} generated.`);
      void download(document.id, document.document_number);
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "Failed to generate the receipt PDF."));
    },
  });

  const busy = mutation.isPending || downloadingId !== null;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap justify-end gap-1.5">
        <button
          type="button"
          onClick={() => {
            setError(null);
            clearFeedback();
            mutation.mutate();
          }}
          disabled={busy}
          title="Generate the receipt PDF (if needed) and download it."
          className={saleSecondaryButton}
          aria-label="Download receipt PDF"
        >
          {busy ? (
            <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
          ) : (
            <Download aria-hidden="true" className="size-3" />
          )}
          <span>
            {mutation.isPending
              ? "Generating…"
              : downloadingId
                ? "Downloading…"
                : "Download PDF"}
          </span>
        </button>
        {issued && (
          <span className="self-center font-mono text-[10px] text-charcoal/50">
            {documentDownloadFilename(issued.document.document_number)}
          </span>
        )}
      </div>
      {(error || downloadError || feedback) && (
        <DocumentFeedbackBanner
          feedback={feedback}
          error={error ?? downloadError}
          onDismiss={() => {
            setError(null);
            clearFeedback();
          }}
        />
      )}
    </div>
  );
}
