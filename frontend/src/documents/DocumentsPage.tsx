import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Ban,
  Download,
  FileText,
  FolderOpen,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { formatDateTime, saleInputClasses, saleLabelClasses, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { documentKeys, fetchDocuments } from "./documentsApi";
import type { DocumentItem, DocumentKind } from "./documentsModel";
import {
  DOCUMENT_KINDS,
  documentKindChipClass,
  documentKindLabel,
  documentStatusTone,
  isVoided,
  shortReference,
} from "./documentsModel";
import { DocumentProofDrawer } from "./DocumentProofDrawer";
import { VoidDocumentDialog } from "./VoidDocumentDialog";
import { DocumentFeedbackBanner } from "./DocumentFeedbackBanner";
import { useDocumentDownload } from "./useDocumentDownload";

/** /admin/documents — the issued-document library with evidence actions. */
export function DocumentsPage() {
  const [kind, setKind] = useState<DocumentKind | "ALL">("ALL");
  const [proofDocument, setProofDocument] = useState<DocumentItem | null>(null);
  const [voidTarget, setVoidTarget] = useState<DocumentItem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: documentKeys.list(kind),
    queryFn: () => fetchDocuments({ kind }),
  });

  const {
    downloadingId,
    feedback,
    error: downloadError,
    clearFeedback,
    download,
  } = useDocumentDownload();

  const documents = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-sans text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
            Documents
          </h1>
          <p className="mt-1 text-sm text-charcoal/65">
            Issued demand letters and receipts with immutable hashes, proofs and voiding.
          </p>
        </div>
        <div>
          <label htmlFor="documents-kind-filter" className={saleLabelClasses}>
            Document kind
          </label>
          <select
            id="documents-kind-filter"
            value={kind}
            onChange={(event) => setKind(event.target.value as DocumentKind | "ALL")}
            className={`${saleInputClasses} mt-1 min-w-44`}
          >
            <option value="ALL">All kinds</option>
            {DOCUMENT_KINDS.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {notice && (
        <div
          role="status"
          className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 shadow-xs"
        >
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-emerald-700/70 hover:text-emerald-900"
          >
            Dismiss
          </button>
        </div>
      )}

      <DocumentFeedbackBanner
        feedback={feedback}
        error={downloadError}
        onDismiss={clearFeedback}
      />

      {isError && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-xs">
          <AlertCircle aria-hidden="true" className="size-8 text-rose-500" />
          <h3 className="text-base font-semibold text-charcoal">
            Failed to load documents
          </h3>
          <p className="text-xs text-charcoal/60">
            {errorMessage(error, "A network or server error occurred.")}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className={saleSecondaryButton}
          >
            <RefreshCw aria-hidden="true" className="size-3.5" />
            <span>Try again</span>
          </button>
        </div>
      )}

      {isLoading && !isError && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-10 text-xs text-charcoal/65 shadow-xs">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading documents…</span>
        </div>
      )}

      {!isLoading && !isError && documents.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-charcoal/10 bg-white p-12 text-center shadow-xs">
          <div className="flex size-12 items-center justify-center rounded-full bg-charcoal/5 text-charcoal/60">
            <FolderOpen aria-hidden="true" className="size-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-charcoal">
            No documents {kind === "ALL" ? "issued yet" : `of kind ${documentKindLabel(kind).toLowerCase()}`}
          </h3>
          <p className="mt-1 max-w-sm text-xs text-charcoal/60">
            Issue demand letters and receipt PDFs from a booking&apos;s payment ledger in
            Sales Bookings. Every issued document appears here with its evidence proof.
          </p>
        </div>
      )}

      {!isLoading && !isError && documents.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <table className="min-w-full text-left text-xs">
            <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/55">
              <tr>
                <th scope="col" className="px-4 py-3">Document</th>
                <th scope="col" className="px-4 py-3">Kind</th>
                <th scope="col" className="px-4 py-3">Reference</th>
                <th scope="col" className="px-4 py-3">Issued at</th>
                <th scope="col" className="px-4 py-3">Issued by</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-charcoal/5">
              {documents.map((document) => {
                const voided = isVoided(document);
                return (
                  <tr key={document.id} className="align-middle">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText aria-hidden="true" className="size-3.5 shrink-0 text-charcoal/40" />
                        <div>
                          <p className="font-semibold whitespace-nowrap text-charcoal">
                            {document.document_number}
                          </p>
                          <p className="mt-0.5 text-[10px] text-charcoal/50">
                            Template v{document.template_version}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${documentKindChipClass(document.kind)}`}
                      >
                        {documentKindLabel(document.kind)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        title={`${document.reference_type} ${document.reference_id}`}
                        className="font-mono text-[11px] text-charcoal/70"
                      >
                        {shortReference(document.reference_id)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-charcoal/75">
                      {formatDateTime(document.issued_at ?? document.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="font-mono text-[11px] text-charcoal/70"
                        title={document.issued_by ?? undefined}
                      >
                        {document.issued_by ? shortReference(document.issued_by) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${documentStatusTone(document.status)}`}
                      >
                        {document.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => void download(document.id, document.document_number)}
                          disabled={voided || downloadingId === document.id}
                          title={voided ? "Voided documents cannot be downloaded (410)." : "Download the PDF with its SHA-256 evidence digest"}
                          className={saleSecondaryButton}
                          aria-label={`Download ${document.document_number}`}
                        >
                          {downloadingId === document.id ? (
                            <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
                          ) : (
                            <Download aria-hidden="true" className="size-3.5" />
                          )}
                          <span>Download</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setProofDocument(document)}
                          className={saleSecondaryButton}
                          aria-label={`View proof for ${document.document_number}`}
                        >
                          <ShieldCheck aria-hidden="true" className="size-3.5" />
                          <span>Proof</span>
                        </button>
                        {!voided && (
                          <button
                            type="button"
                            onClick={() => setVoidTarget(document)}
                            className={`${saleSecondaryButton} border-rose-200 text-rose-700 hover:bg-rose-50`}
                            aria-label={`Void ${document.document_number}`}
                          >
                            <Ban aria-hidden="true" className="size-3.5" />
                            <span>Void</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="border-t border-charcoal/10 px-4 py-2.5 text-[11px] text-charcoal/55">
            {total} document{total === 1 ? "" : "s"}
            {kind === "ALL" ? "" : ` · filtered to ${documentKindLabel(kind).toLowerCase()}s`}
          </p>
        </div>
      )}

      {proofDocument && (
        <DocumentProofDrawer
          documentId={proofDocument.id}
          documentNumber={proofDocument.document_number}
          onClose={() => setProofDocument(null)}
        />
      )}

      {voidTarget && (
        <VoidDocumentDialog
          document={voidTarget}
          onClose={() => setVoidTarget(null)}
          onVoided={async (message) => {
            setVoidTarget(null);
            setNotice(message);
            await refetch();
          }}
        />
      )}
    </div>
  );
}
