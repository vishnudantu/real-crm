import { CheckCircle2, X } from "lucide-react";
import type { DocumentDownloadFeedback } from "./useDocumentDownload";

interface DocumentFeedbackBannerProps {
  feedback: DocumentDownloadFeedback | null;
  error: string | null;
  onDismiss: () => void;
}

/** Success toast carrying the download's SHA-256 digest, or an inline error. */
export function DocumentFeedbackBanner({
  feedback,
  error,
  onDismiss,
}: DocumentFeedbackBannerProps) {
  if (!feedback && !error) return null;

  if (error) {
    return (
      <div
        role="alert"
        className="flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700 shadow-xs"
      >
        <span>{error}</span>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss download error"
          className="text-rose-700/70 hover:text-rose-900"
        >
          <X aria-hidden="true" className="size-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 shadow-xs"
    >
      <div className="flex min-w-0 items-start gap-2">
        <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald-600" />
        <div className="min-w-0">
          <p>{feedback?.message}</p>
          {feedback?.sha256 && (
            <p className="mt-1 break-all font-mono text-[10.5px] font-normal text-emerald-800/80">
              SHA-256 {feedback.sha256}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss download confirmation"
        className="text-emerald-700/70 hover:text-emerald-900"
      >
        <X aria-hidden="true" className="size-3.5" />
      </button>
    </div>
  );
}
