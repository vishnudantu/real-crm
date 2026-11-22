import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  FileText,
  LoaderCircle,
  RefreshCw,
  X,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import {
  saleCardClasses,
  saleSecondaryButton,
  formatDateTime,
} from "../admin/sales/salesBookingUi";
import { documentKeys, fetchDocumentProof } from "./documentsApi";
import {
  documentStatusTone,
  extractProofFields,
  formatPayloadSnapshot,
  isVoided,
} from "./documentsModel";

interface DocumentProofDrawerProps {
  documentId: string;
  documentNumber: string;
  onClose: () => void;
}

/** Side drawer showing the evidence proof for one issued document. */
export function DocumentProofDrawer({
  documentId,
  documentNumber,
  onClose,
}: DocumentProofDrawerProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [snapshotOpen, setSnapshotOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: documentKeys.proof(documentId),
    queryFn: () => fetchDocumentProof(documentId),
  });

  const proof = data ?? null;
  const fields = extractProofFields(proof?.payload_snapshot);

  const handleCopyHash = async () => {
    if (!proof) return;
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(proof.content_sha256);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError("Clipboard is unavailable. Select the hash text to copy it.");
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-stretch justify-end bg-charcoal/45 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Evidence proof for ${documentNumber}`}
        className="flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Document proof
            </h2>
            <p className="mt-0.5 text-[11px] text-charcoal/60">{documentNumber}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document proof"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-charcoal/65">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              <span>Loading proof…</span>
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center gap-2 rounded-2xl border border-rose-200 bg-white p-6 text-center">
              <AlertCircle aria-hidden="true" className="size-6 text-rose-500" />
              <p className="text-xs text-charcoal/70">
                {errorMessage(error, "Failed to load the document proof.")}
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className={saleSecondaryButton}
              >
                <RefreshCw aria-hidden="true" className="size-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {proof && (
            <div className="space-y-4">
              <section className={`${saleCardClasses} p-4`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <FileText aria-hidden="true" className="size-4 text-charcoal/50" />
                    <h3 className="text-sm font-semibold text-charcoal">
                      {proof.document_number}
                    </h3>
                  </div>
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${documentStatusTone(proof.status)}`}
                  >
                    {proof.status}
                  </span>
                </div>
                <dl className="mt-3 grid gap-3 text-[11px] sm:grid-cols-2">
                  <div>
                    <dt className="text-charcoal/55">Template version</dt>
                    <dd className="mt-0.5 font-medium text-charcoal">
                      v{proof.template_version}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-charcoal/55">Issued at</dt>
                    <dd className="mt-0.5 font-medium text-charcoal">
                      {formatDateTime(proof.issued_at)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-charcoal/55">Issued by (user id)</dt>
                    <dd className="mt-0.5 break-all font-mono text-[10.5px] text-charcoal">
                      {proof.issued_by ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-charcoal/55">Document id</dt>
                    <dd className="mt-0.5 break-all font-mono text-[10.5px] text-charcoal">
                      {proof.id}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className={`${saleCardClasses} p-4`}>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-charcoal/60">
                    SHA-256 content digest
                  </h3>
                  <button
                    type="button"
                    onClick={() => void handleCopyHash()}
                    className={saleSecondaryButton}
                    aria-label="Copy document hash"
                  >
                    {copied ? (
                      <Check aria-hidden="true" className="size-3.5 text-emerald-600" />
                    ) : (
                      <Copy aria-hidden="true" className="size-3.5" />
                    )}
                    <span>{copied ? "Copied" : "Copy hash"}</span>
                  </button>
                </div>
                <p className="mt-2.5 break-all rounded-xl border border-charcoal/10 bg-charcoal/[0.03] p-3 font-mono text-[11px] leading-5 text-charcoal">
                  {proof.content_sha256}
                </p>
                {copyError && (
                  <p role="alert" className="mt-2 text-[11px] text-rose-600">
                    {copyError}
                  </p>
                )}
              </section>

              {isVoided(proof) && (
                <section className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-rose-700">
                    Voided
                  </h3>
                  <p className="mt-2 text-[11px] text-rose-700">
                    Voided at {formatDateTime(proof.voided_at)}
                  </p>
                  <p className="mt-1 text-xs whitespace-pre-wrap text-rose-800">
                    {proof.void_reason ?? "No reason recorded."}
                  </p>
                </section>
              )}

              <section className={`${saleCardClasses} p-4`}>
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-charcoal/60">
                  Issue-time snapshot
                </h3>
                {fields.length === 0 ? (
                  <p className="mt-2 text-[11px] text-charcoal/60">
                    No snapshot fields were recorded for this document.
                  </p>
                ) : (
                  <dl className="mt-3 grid gap-x-4 gap-y-3 text-[11px] sm:grid-cols-2">
                    {fields.map((field) => (
                      <div key={field.key}>
                        <dt className="text-charcoal/55">{field.label}</dt>
                        <dd className="mt-0.5 font-medium break-words text-charcoal">
                          {field.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
                <div className="mt-4 border-t border-charcoal/10 pt-3">
                  <button
                    type="button"
                    onClick={() => setSnapshotOpen((open) => !open)}
                    aria-expanded={snapshotOpen}
                    className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-charcoal/70 hover:text-charcoal"
                  >
                    {snapshotOpen ? (
                      <ChevronUp aria-hidden="true" className="size-3.5" />
                    ) : (
                      <ChevronDown aria-hidden="true" className="size-3.5" />
                    )}
                    <span>{snapshotOpen ? "Hide raw snapshot" : "Show raw snapshot"}</span>
                  </button>
                  {snapshotOpen && (
                    <pre className="mt-2.5 max-h-80 overflow-auto rounded-xl border border-charcoal/10 bg-charcoal/[0.03] p-3 font-mono text-[10.5px] leading-5 whitespace-pre-wrap break-words text-charcoal/85">
                      {formatPayloadSnapshot(proof.payload_snapshot)}
                    </pre>
                  )}
                </div>
              </section>

              <p className="text-[10.5px] leading-5 text-charcoal/50">
                Bank account numbers are masked in the stored evidence. Downloads of
                voided documents are blocked by the API; the digest above lets you verify
                any copy of this PDF.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
