import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Download,
  FileCheck2,
  FileText,
  Info,
  LoaderCircle,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { ApiError } from "../../auth/api";
import { getSession } from "../../auth/session";
import { errorMessage } from "../../shared/apiRequest";
import { useBuyerUser } from "../BuyerAuthGuard";
import {
  buyerDocumentKeys,
  downloadBuyerDocument,
  fetchBuyerDocumentRequests,
  fetchBuyerDocuments,
  uploadBuyerDocument,
} from "./buyerDocumentsApi";
import {
  categoryLabel,
  documentStatusLabel,
  documentStatusTone,
  formatBytes,
  isOpenRequest,
  requestStatusTone,
  type DocumentRequest,
} from "./buyerDocumentsModel";
import { UploadDocumentDialog } from "./UploadDocumentDialog";

export function BuyerDocumentsPage() {
  const { user } = useBuyerUser();
  const queryClient = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [fulfillingRequest, setFulfillingRequest] =
    useState<DocumentRequest | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const documentsQuery = useQuery({
    queryKey: buyerDocumentKeys.list(),
    queryFn: () => fetchBuyerDocuments(),
  });

  const requestsQuery = useQuery({
    queryKey: buyerDocumentKeys.requests(),
    queryFn: () => fetchBuyerDocumentRequests(),
  });

  const uploadMutation = useMutation({
    mutationFn: uploadBuyerDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: buyerDocumentKeys.all });
      setUploadOpen(false);
      setFulfillingRequest(null);
      setFeedback("Your document was uploaded and is now awaiting review.");
    },
  });

  const pendingRequests =
    requestsQuery.data?.items.filter(isOpenRequest) ?? [];

  const handleDownload = async (document: {
    id: string;
    title: string;
    content_type: string;
  }) => {
    setFeedback(null);
    setDownloadingId(document.id);
    try {
      const result = await downloadBuyerDocument(document, getSession());
      setFeedback(`${result.fileName} downloaded.`);
    } catch (downloadError: unknown) {
      setFeedback(
        errorMessage(downloadError, "Failed to download the document."),
      );
    } finally {
      setDownloadingId(null);
    }
  };

  const openUpload = () => {
    setFeedback(null);
    setFulfillingRequest(null);
    setUploadOpen(true);
  };

  const openFulfill = (request: DocumentRequest) => {
    setFeedback(null);
    setFulfillingRequest(request);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div className="space-y-1.5">
          <span className="eyebrow">Document vault</span>
          <h1 className="font-sans font-semibold tracking-tight text-3xl text-charcoal">
            My Documents
          </h1>
          <p className="max-w-xl text-sm text-charcoal/70">
            Securely upload identity, income and property documents, and track
            their verification with your {user.full_name.split(" ")[0]} concierge.
          </p>
        </div>
        <button
          type="button"
          onClick={openUpload}
          className="inline-flex min-h-11 items-center justify-center gap-2 self-start rounded-xl bg-forest px-5 text-sm font-semibold text-ivory shadow-xs transition-colors hover:bg-forest-deep sm:self-auto"
        >
          <Upload className="size-4" />
          Upload document
        </button>
      </section>

      {/* Transient feedback toast */}
      {feedback && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl border border-forest/25 bg-forest/5 px-4 py-3 text-sm text-forest"
        >
          <Info className="mt-0.5 size-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Pending staff requests */}
      <PendingRequestsSection
        isLoading={requestsQuery.isLoading}
        error={requestsQuery.error}
        requests={pendingRequests}
        onFulfill={openFulfill}
      />

      {/* Documents list */}
      <section aria-labelledby="documents-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2
            id="documents-heading"
            className="font-sans font-semibold tracking-tight text-xl text-charcoal"
          >
            Uploaded documents
          </h2>
          {documentsQuery.data && (
            <span className="text-xs text-charcoal/50">
              {documentsQuery.data.total}{" "}
              {documentsQuery.data.total === 1 ? "document" : "documents"}
            </span>
          )}
        </div>

        {documentsQuery.isLoading ? (
          <LoadingCard label="Loading your documents…" />
        ) : documentsQuery.isError ? (
          <BackendNotice error={documentsQuery.error} />
        ) : documentsQuery.data && documentsQuery.data.items.length > 0 ? (
          <ul className="space-y-3">
            {documentsQuery.data.items.map((document) => (
              <li
                key={document.id}
                className="flex flex-col gap-4 rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-3.5">
                  <div className="grid size-11 shrink-0 place-items-center rounded-xl border border-charcoal/10 bg-ivory text-forest">
                    <FileText className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-semibold text-charcoal">
                        {document.title}
                      </h3>
                      <span
                        className={`rounded-full border px-2.5 py-0.5 text-[0.68rem] font-semibold ${documentStatusTone(document.status)}`}
                      >
                        {documentStatusLabel(document.status)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-charcoal/60">
                      <span>{categoryLabel(document.category)}</span>
                      <span aria-hidden="true">·</span>
                      <span>{formatBytes(document.size_bytes)}</span>
                      <span aria-hidden="true">·</span>
                      <span>
                        Uploaded{" "}
                        {new Date(document.created_at).toLocaleDateString([], {
                          dateStyle: "medium",
                        })}
                      </span>
                    </div>
                    {document.status === "REJECTED" && document.review_note && (
                      <p className="mt-1.5 text-xs text-rose-700">
                        Reviewer note: {document.review_note}
                      </p>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleDownload(document)}
                  disabled={downloadingId === document.id}
                  className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 self-start rounded-xl border border-charcoal/15 bg-ivory px-4 text-xs font-semibold text-charcoal transition-colors hover:border-forest hover:text-forest disabled:opacity-50 sm:self-auto"
                >
                  {downloadingId === document.id ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Download className="size-4" />
                  )}
                  Download
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyDocumentsCard onUpload={openUpload} />
        )}
      </section>

      <UploadDocumentDialog
        open={uploadOpen || fulfillingRequest !== null}
        lockedCategory={fulfillingRequest?.category}
        initialTitle={fulfillingRequest?.title}
        onClose={() => {
          if (!uploadMutation.isPending) {
            setUploadOpen(false);
            setFulfillingRequest(null);
          }
        }}
        onUpload={async (input) => {
          await uploadMutation.mutateAsync(input);
        }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */

function PendingRequestsSection({
  isLoading,
  error,
  requests,
  onFulfill,
}: {
  isLoading: boolean;
  error: Error | null;
  requests: DocumentRequest[];
  onFulfill: (request: DocumentRequest) => void;
}) {
  if (isLoading) {
    return <LoadingCard label="Checking for document requests…" />;
  }
  if (error) {
    // The whole section may be unavailable until buyer endpoints ship; the
    // documents section surfaces the same notice, so stay quiet here.
    return null;
  }
  if (requests.length === 0) return null;

  return (
    <section
      aria-labelledby="requests-heading"
      className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-5"
    >
      <div className="flex items-center gap-2">
        <CalendarClock className="size-4.5 text-amber-700" />
        <h2
          id="requests-heading"
          className="text-sm font-semibold text-amber-900"
        >
          Staff requested these documents from you
        </h2>
      </div>
      <ul className="space-y-2.5">
        {requests.map((request) => (
          <li
            key={request.id}
            className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-charcoal">
                  {request.title}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[0.65rem] font-semibold ${requestStatusTone(request.status)}`}
                >
                  {request.status}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-charcoal/65">
                {categoryLabel(request.category)}
                {request.due_date && (
                  <>
                    {" · due "}
                    {new Date(request.due_date).toLocaleDateString([], {
                      dateStyle: "medium",
                    })}
                  </>
                )}
              </p>
              {request.notes && (
                <p className="mt-1 text-xs text-charcoal/60 italic">
                  “{request.notes}”
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => onFulfill(request)}
              className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 self-start rounded-xl bg-forest px-4 text-xs font-semibold text-ivory transition-colors hover:bg-forest-deep sm:self-auto"
            >
              <Upload className="size-3.5" />
              Upload
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ */

function LoadingCard({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-3 rounded-2xl border border-charcoal/10 bg-white p-10 text-sm text-charcoal/60"
    >
      <LoaderCircle className="size-4 animate-spin text-forest" />
      {label}
    </div>
  );
}

function EmptyDocumentsCard({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-charcoal/20 bg-ivory/40 p-10 text-center">
      <FileCheck2 className="mx-auto size-9 text-charcoal/30" />
      <p className="mt-3 text-sm font-semibold text-charcoal">
        No documents yet
      </p>
      <p className="mx-auto mt-1 max-w-sm text-xs text-charcoal/60">
        Upload your first document to get it verified. Accepted files are PDF or
        image, and photos are compressed automatically before they leave your
        device.
      </p>
      <button
        type="button"
        onClick={onUpload}
        className="mt-4 inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-forest px-5 text-xs font-semibold text-ivory hover:bg-forest-deep"
      >
        <Upload className="size-3.5" />
        Upload document
      </button>
    </div>
  );
}

/**
 * Shown when the document list cannot load. A 404 on the /mine routes means the
 * account is not yet matched to a customer record (the backend resolves the
 * buyer's contact from email/phone), so we explain that state instead of
 * showing a generic error.
 */
function BackendNotice({ error }: { error: Error }) {
  const isUnlinked = error instanceof ApiError && error.status === 404;
  return (
    <div
      role={isUnlinked ? undefined : "alert"}
      className={`rounded-2xl border p-6 ${
        isUnlinked
          ? "border-sand/40 bg-sand/10"
          : "border-rose-200 bg-rose-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <ShieldAlert
          className={`mt-0.5 size-5 shrink-0 ${
            isUnlinked ? "text-sand" : "text-rose-700"
          }`}
        />
        <div>
          <h3
            className={`text-sm font-semibold ${
              isUnlinked ? "text-charcoal" : "text-rose-800"
            }`}
          >
            {isUnlinked
              ? "Your account isn't linked to a customer record yet"
              : "We couldn't load your documents"}
          </h3>
          <p
            className={`mt-1 text-xs leading-relaxed ${
              isUnlinked ? "text-charcoal/75" : "text-rose-700"
            }`}
          >
            {isUnlinked
              ? "Please use the same email or phone your sales executive has on file, or ask them to link your account — then your documents and requests appear here."
              : errorMessage(error, "Something went wrong. Please try again.")}
          </p>
        </div>
      </div>
    </div>
  );
}
