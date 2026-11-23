import { useQuery } from "@tanstack/react-query";
import { BookOpen, Lightbulb, LoaderCircle } from "lucide-react";
import { saleCardClasses } from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { fetchTicketSuggestions, kbKeys } from "./serviceDeskApi";

/** Ticket drawer panel: top-3 published KB articles matching the subject. */
export function ArticleSuggestionsPanel({ ticketId }: { ticketId: string }) {
  const query = useQuery({
    queryKey: kbKeys.suggestions(ticketId),
    queryFn: () => fetchTicketSuggestions(ticketId),
    staleTime: 30_000,
  });

  return (
    <section className={`${saleCardClasses} p-4`} aria-label="Suggested knowledge base articles">
      <h3 className="flex items-center gap-2 text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
        <Lightbulb aria-hidden="true" className="size-3.5 text-amber-500" />
        Suggested articles
      </h3>

      {query.isLoading && (
        <div className="flex items-center gap-2 py-3 text-[11px] text-charcoal/55">
          <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
          <span>Finding matches…</span>
        </div>
      )}
      {query.isError && (
        <p className="py-3 text-[11px] text-rose-700">
          {errorMessage(query.error, "Suggestions could not be loaded.")}
        </p>
      )}
      {query.data && query.data.length === 0 && (
        <p className="py-3 text-[11px] text-charcoal/55">
          No published articles match this subject yet.
        </p>
      )}
      {query.data && query.data.length > 0 && (
        <ul className="mt-2 space-y-2">
          {query.data.map((suggestion) => (
            <li
              key={suggestion.article_id}
              className="flex items-start gap-2 rounded-xl border border-charcoal/10 bg-white px-3 py-2"
            >
              <BookOpen aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-forest" />
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-charcoal" title={suggestion.title}>
                  {suggestion.title}
                </p>
                <p className="mt-0.5 text-[10.5px] text-charcoal/55">
                  {suggestion.category} · /{suggestion.slug}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
