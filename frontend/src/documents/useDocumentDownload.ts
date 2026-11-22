import { useState } from "react";
import { getSession } from "../auth/session";
import { errorMessage } from "../shared/apiRequest";
import { downloadDocument } from "./documentsApi";
import { documentDownloadFilename } from "./documentsModel";

export interface DocumentDownloadFeedback {
  message: string;
  sha256?: string;
}

interface UseDocumentDownloadResult {
  downloadingId: string | null;
  feedback: DocumentDownloadFeedback | null;
  error: string | null;
  clearFeedback: () => void;
  download: (id: string, documentNumber: string) => Promise<void>;
}

/**
 * Shared authenticated-download flow: bearer fetch, object-URL download and a
 * success toast carrying the X-Document-Sha256 evidence digest.
 */
export function useDocumentDownload(): UseDocumentDownloadResult {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<DocumentDownloadFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async (id: string, documentNumber: string) => {
    setError(null);
    setDownloadingId(id);
    try {
      const result = await downloadDocument(
        id,
        getSession(),
        documentDownloadFilename(documentNumber),
      );
      setFeedback({
        message: `${result.fileName} downloaded.`,
        sha256: result.sha256,
      });
    } catch (downloadError: unknown) {
      setError(errorMessage(downloadError, "Failed to download the document."));
    } finally {
      setDownloadingId(null);
    }
  };

  return {
    downloadingId,
    feedback,
    error,
    clearFeedback: () => {
      setFeedback(null);
      setError(null);
    },
    download,
  };
}
