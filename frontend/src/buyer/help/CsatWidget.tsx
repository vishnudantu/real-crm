import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Star } from "lucide-react";
import { ApiError } from "../../auth/api";
import { errorMessage } from "../../shared/apiRequest";
import type { TicketSatisfaction } from "../../servicedesk/serviceDeskModel";
import { helpKeys, submitTicketSatisfaction } from "./helpCenterApi";
import { CSAT_RATING_LABELS, validateCsatSubmission } from "./helpCenterModel";

interface CsatWidgetProps {
  ticketId: string;
  ticketNumber: string;
  existing: TicketSatisfaction | null;
}

/** 1-5 star rating + optional note for a closed ticket (buyer portal). */
export function CsatWidget({ ticketId, ticketNumber, existing }: CsatWidgetProps) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState<number | null>(existing?.rating ?? null);
  const [feedback, setFeedback] = useState(existing?.feedback ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(Boolean(existing?.rating));

  const mutation = useMutation({
    mutationFn: () => {
      const validation = validateCsatSubmission(rating, feedback);
      if (validation) throw new ApiError(0, "VALIDATION", validation);
      return submitTicketSatisfaction({
        ticketId,
        rating: rating as number,
        feedback: feedback.trim() || null,
      });
    },
    onSuccess: (survey) => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: helpKeys.ticket(ticketId) });
      queryClient.setQueryData<TicketSatisfaction | undefined>(
        [...helpKeys.ticket(ticketId), "satisfaction"],
        survey,
      );
    },
    onError: (submitError: unknown) => {
      setError(
        errorMessage(
          submitError,
          submitError instanceof ApiError && submitError.status === 409
            ? "This ticket is not closed yet, so ratings are still open."
            : "Your rating could not be saved. Please try again.",
        ),
      );
    },
  });

  return (
    <div className="rounded-xl border border-charcoal/10 bg-white p-4 shadow-xs">
      <h3 className="text-sm font-semibold text-charcoal">How was your experience?</h3>
      <p className="mt-1 text-[11.5px] text-charcoal/60">
        Ticket {ticketNumber} is closed — your feedback is optional but helps the desk improve.
      </p>

      <div className="mt-3 flex items-center gap-1" role="radiogroup" aria-label="Satisfaction rating">
        {[1, 2, 3, 4, 5].map((value) => {
          const filled = rating !== null && value <= rating;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              aria-label={`${value} star${value === 1 ? "" : "s"} — ${CSAT_RATING_LABELS[value]}`}
              onClick={() => {
                setRating(value);
                setSaved(false);
                setError(null);
              }}
              className="rounded-lg p-1 transition-colors hover:bg-amber-50"
            >
              <Star
                aria-hidden="true"
                className={`size-6 ${
                  filled ? "fill-amber-400 text-amber-500" : "text-charcoal/25"
                }`}
              />
            </button>
          );
        })}
        {rating !== null && (
          <span className="ml-2 text-[11px] font-medium text-charcoal/60">
            {CSAT_RATING_LABELS[rating]}
          </span>
        )}
      </div>

      <textarea
        rows={2}
        maxLength={2000}
        value={feedback}
        onChange={(event) => {
          setFeedback(event.target.value);
          setSaved(false);
        }}
        placeholder="Anything you want us to know? (optional)"
        aria-label="Feedback note"
        className="mt-3 w-full rounded-xl border border-charcoal/15 bg-[#FAFAF7] px-3 py-2 text-xs text-charcoal placeholder:text-charcoal/40 focus:border-forest focus:outline-none"
      />

      {error && (
        <p role="alert" className="mt-2 text-[11px] font-medium text-rose-700">
          {error}
        </p>
      )}

      <div className="mt-3 flex items-center justify-between gap-3">
        {saved && (
          <p className="text-[11px] text-emerald-700" role="status">
            Thanks for your feedback — you can change it anytime.
          </p>
        )}
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || rating === null}
          className={`inline-flex items-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-xs font-semibold text-ivory shadow-xs transition hover:bg-forest/90 disabled:opacity-50 ${saved ? "" : "ml-auto"}`}
        >
          {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
          <span>{mutation.isPending ? "Saving…" : existing?.rating ? "Update rating" : "Submit rating"}</span>
        </button>
      </div>
    </div>
  );
}
