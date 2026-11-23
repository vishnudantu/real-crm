import { useEffect, useId, useRef, useState } from "react";
import { LoaderCircle, UploadCloud, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import {
  ACCEPTED_DOCUMENT_TYPES,
  ACCEPTED_DOCUMENT_TYPES_LABEL,
  BUYER_DOCUMENT_CATEGORIES,
  MAX_DOCUMENT_SIZE_LABEL,
  formatBytes,
  shouldCompress,
  validateUploadFile,
  type BuyerDocumentCategory,
} from "./buyerDocumentsModel";
import { prepareUpload } from "./imageCompress";

export interface UploadDocumentDialogProps {
  open: boolean;
  /** When fulfilling a staff request, the category is preselected and locked. */
  lockedCategory?: BuyerDocumentCategory;
  initialTitle?: string;
  /** contact_id resolved for the buyer. If null, uploads are blocked. */
  contactId: string | null;
  onClose: () => void;
  onUpload: (input: {
    contactId: string;
    category: BuyerDocumentCategory;
    title: string;
    blob: Blob;
    contentType: string;
  }) => Promise<void>;
}

export function UploadDocumentDialog({
  open,
  lockedCategory,
  initialTitle,
  contactId,
  onClose,
  onUpload,
}: UploadDocumentDialogProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const [category, setCategory] = useState<BuyerDocumentCategory>(
    lockedCategory ?? "IDENTITY",
  );
  const [title, setTitle] = useState(initialTitle ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setCategory(lockedCategory ?? "IDENTITY");
      setTitle(initialTitle ?? "");
      setFile(null);
      setError(null);
      setBusy(false);
    }
  }, [open, lockedCategory, initialTitle]);

  if (!open) return null;

  const handleFileChange = (picked: File | null) => {
    setError(null);
    if (!picked) {
      setFile(null);
      return;
    }
    const validation = validateUploadFile(picked);
    if (validation) {
      setError(validation);
      setFile(null);
      return;
    }
    setFile(picked);
    if (!title.trim()) {
      setTitle(picked.name.replace(/\.[^.]+$/, ""));
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!contactId) {
      setError(
        "We couldn't match your account to a customer record yet. Please contact our team so they can link your documents.",
      );
      return;
    }
    if (!file) {
      setError("Please choose a file to upload.");
      return;
    }
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError("Please give this document a name.");
      return;
    }
    const validation = validateUploadFile(file);
    if (validation) {
      setError(validation);
      return;
    }

    setBusy(true);
    try {
      const prepared = await prepareUpload(file);
      await onUpload({
        contactId,
        category,
        title: trimmedTitle,
        blob: prepared.blob,
        contentType: prepared.contentType,
      });
    } catch (uploadError: unknown) {
      setError(
        uploadError instanceof Error && uploadError.message
          ? uploadError.message
          : "The document could not be uploaded. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/50 p-4 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${titleId}-heading`}
        className="w-full max-w-md rounded-2xl border border-charcoal/10 bg-white p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between">
          <div>
            <span className="eyebrow">Secure upload</span>
            <h2
              id={`${titleId}-heading`}
              className="mt-1 font-sans font-semibold tracking-tight text-xl text-charcoal"
            >
              {lockedCategory ? "Fulfil document request" : "Upload a document"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-charcoal/60 hover:bg-charcoal/5 disabled:opacity-50"
          >
            <X className="size-4.5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label
              htmlFor={`${titleId}-category`}
              className="mb-1.5 block text-xs font-semibold text-charcoal/70"
            >
              Document type
            </label>
            <select
              id={`${titleId}-category`}
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as BuyerDocumentCategory)
              }
              disabled={Boolean(lockedCategory) || busy}
              className="w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal focus:border-forest focus:outline-none disabled:bg-ivory/60"
            >
              {BUYER_DOCUMENT_CATEGORIES.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor={`${titleId}-title`}
              className="mb-1.5 block text-xs font-semibold text-charcoal/70"
            >
              Document name
            </label>
            <input
              id={`${titleId}-title`}
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={255}
              disabled={busy}
              placeholder="e.g. Aadhaar card, bank statement"
              className="w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal placeholder:text-charcoal/40 focus:border-forest focus:outline-none disabled:opacity-60"
            />
          </div>

          <div>
            <span className="mb-1.5 block text-xs font-semibold text-charcoal/70">
              File
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_DOCUMENT_TYPES}
              className="hidden"
              onChange={(event) =>
                handleFileChange(event.target.files?.[0] ?? null)
              }
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={busy}
              className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-charcoal/25 bg-ivory/40 px-4 py-6 text-center transition-colors hover:border-forest hover:bg-ivory disabled:opacity-60"
            >
              <UploadCloud className="size-7 text-forest" />
              {file ? (
                <>
                  <span className="text-sm font-semibold text-charcoal">
                    {file.name}
                  </span>
                  <span className="text-xs text-charcoal/60">
                    {formatBytes(file.size)}
                    {shouldCompress(file.type) ? " · images are compressed on upload" : ""}
                  </span>
                </>
              ) : (
                <>
                  <span className="text-sm font-medium text-charcoal/80">
                    Choose a file
                  </span>
                  <span className="text-xs text-charcoal/55">
                    {ACCEPTED_DOCUMENT_TYPES_LABEL} · up to {MAX_DOCUMENT_SIZE_LABEL}
                  </span>
                </>
              )}
            </button>
            <p className="mt-1.5 text-[0.7rem] text-charcoal/50">
              Photos are resized and compressed on your device before upload to
              keep files small. PDFs are uploaded unchanged.
            </p>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800"
            >
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="flex-1 rounded-xl border border-charcoal/15 px-4 py-2.5 text-sm font-semibold text-charcoal/75 hover:bg-charcoal/5 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !file}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest px-4 py-2.5 text-sm font-semibold text-ivory hover:bg-forest-deep disabled:opacity-50"
            >
              {busy && <LoaderCircle className="size-4 animate-spin" />}
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
