import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertCircle,
  BookOpen,
  LifeBuoy,
  LoaderCircle,
  Search,
  Ticket,
} from "lucide-react";
import { errorMessage } from "../../shared/apiRequest";
import { CsatWidget } from "./CsatWidget";
import { fetchHelpArticles, fetchMyTicket, fetchMyTickets, helpKeys } from "./helpCenterApi";
import type { HelpArticle } from "./helpCenterModel";
import {
  isRatingEligible,
  kbMarkdownBlocks,
  normalizeHelpQuery,
} from "./helpCenterModel";

/** /buyer/help — published knowledge base search + CSAT on closed tickets. */
export function HelpCenterPage() {
  const [query, setQuery] = useState("");
  const [pendingQuery, setPendingQuery] = useState("");
  const [openArticleId, setOpenArticleId] = useState<string | null>(null);

  const articlesQuery = useQuery({
    queryKey: helpKeys.articles(pendingQuery),
    queryFn: () => fetchHelpArticles({ search: pendingQuery }),
    staleTime: 60_000,
  });
  const ticketsQuery = useQuery({
    queryKey: helpKeys.tickets(),
    queryFn: fetchMyTickets,
    staleTime: 30_000,
  });

  const articles = articlesQuery.data?.items ?? [];
  const openArticle = useMemo(
    () => articles.find((article) => article.id === openArticleId) ?? null,
    [articles, openArticleId],
  );
  const closedTickets = (ticketsQuery.data?.items ?? []).filter(isRatingEligible);

  if (openArticle) {
    return <ArticleReader article={openArticle} onBack={() => setOpenArticleId(null)} />;
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="flex items-center gap-2.5 font-sans text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
          <LifeBuoy aria-hidden="true" className="size-6 text-forest" />
          Help Center
        </h1>
        <p className="mt-1.5 text-sm text-charcoal/65">
          Guides our team published for you — search by keyword or browse below.
        </p>
      </section>

      <form
        aria-label="Search help articles"
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setPendingQuery(normalizeHelpQuery(query));
        }}
      >
        <div className="relative flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-charcoal/40"
          />
          <input
            type="search"
            value={query}
            maxLength={200}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. loan, possession, payment…"
            aria-label="Search keywords"
            className="w-full rounded-xl border border-charcoal/15 bg-white py-2.5 pr-3 pl-9 text-sm text-charcoal shadow-xs placeholder:text-charcoal/40 focus:border-forest focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="rounded-xl bg-forest px-4 py-2.5 text-sm font-semibold text-ivory shadow-xs transition hover:bg-forest/90"
        >
          Search
        </button>
      </form>

      {articlesQuery.isError && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-xs">
          <AlertCircle aria-hidden="true" className="size-7 text-rose-500" />
          <p className="text-xs text-charcoal/65">
            {errorMessage(articlesQuery.error, "The help center could not be loaded.")}
          </p>
          <button
            type="button"
            onClick={() => void articlesQuery.refetch()}
            className="rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-xs font-semibold text-charcoal/80 hover:bg-charcoal/5"
          >
            Try again
          </button>
        </div>
      )}

      {articlesQuery.isLoading && !articlesQuery.isError && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-10 text-xs text-charcoal/60 shadow-xs">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading articles…</span>
        </div>
      )}

      {!articlesQuery.isLoading && !articlesQuery.isError && articles.length === 0 && (
        <div className="flex flex-col items-center rounded-2xl border border-charcoal/10 bg-white p-10 text-center shadow-xs">
          <BookOpen aria-hidden="true" className="size-7 text-charcoal/30" />
          <h2 className="mt-2 text-sm font-semibold text-charcoal">
            {pendingQuery ? `No guides match “${pendingQuery}”` : "No guides published yet"}
          </h2>
          <p className="mt-1 text-xs text-charcoal/55">
            {pendingQuery
              ? "Try a shorter keyword, or ask your relationship manager."
              : "Our team has not published help articles yet."}
          </p>
        </div>
      )}

      {articles.length > 0 && (
        <section aria-label="Help articles">
          <h2 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
            {pendingQuery ? `${articles.length} result${articles.length === 1 ? "" : "s"}` : "All guides"}
          </h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {articles.map((article) => (
              <li key={article.id}>
                <button
                  type="button"
                  onClick={() => setOpenArticleId(article.id)}
                  className="group flex w-full flex-col items-start gap-1.5 rounded-2xl border border-charcoal/10 bg-white p-4 text-left shadow-xs transition hover:border-forest/40 hover:shadow-sm"
                >
                  <span className="text-sm font-semibold text-charcoal group-hover:text-forest">
                    {article.title}
                  </span>
                  <span className="rounded-full border border-charcoal/10 bg-[#FAFAF7] px-2 py-0.5 text-[10px] font-semibold tracking-wider text-charcoal/60 uppercase">
                    {article.category}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Rate closed tickets">
        <h2 className="flex items-center gap-2 text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
          <Ticket aria-hidden="true" className="size-3.5" />
          Closed support tickets
        </h2>
        {ticketsQuery.isLoading && (
          <div className="mt-3 flex items-center gap-2 text-xs text-charcoal/55">
            <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
            Loading your tickets…
          </div>
        )}
        {!ticketsQuery.isLoading && closedTickets.length === 0 && (
          <p className="mt-2 text-xs text-charcoal/55">
            You have no closed tickets to rate right now.
          </p>
        )}
        <div className="mt-3 space-y-3">
          {closedTickets.map((ticket) => (
            <TicketRatingCard key={ticket.id} ticket={ticket} />
          ))}
        </div>
      </section>
    </div>
  );
}

/** Loads the buyer's own ticket detail so the widget shows the saved rating. */
function TicketRatingCard({
  ticket,
}: {
  ticket: { id: string; ticket_number: string; subject: string };
}) {
  const detailQuery = useQuery({
    queryKey: helpKeys.ticket(ticket.id),
    queryFn: () => fetchMyTicket(ticket.id),
    staleTime: 30_000,
  });
  return (
    <div className="rounded-2xl border border-charcoal/10 bg-[#FAFAF7] p-4 shadow-xs">
      <p className="text-xs font-semibold text-charcoal">
        {ticket.ticket_number} — {ticket.subject}
      </p>
      <div className="mt-3">
        <CsatWidget
          ticketId={ticket.id}
          ticketNumber={ticket.ticket_number}
          existing={detailQuery.data?.satisfaction ?? null}
        />
      </div>
    </div>
  );
}

function ArticleReader({ article, onBack }: { article: HelpArticle; onBack: () => void }) {
  const blocks = kbMarkdownBlocks(article.body_markdown);
  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal/60 hover:text-charcoal"
      >
        <ArrowLeft aria-hidden="true" className="size-3.5" />
        Back to Help Center
      </button>
      <header>
        <p className="text-[10px] font-semibold tracking-wider text-forest uppercase">
          {article.category}
        </p>
        <h1 className="mt-1.5 font-sans text-2xl font-semibold tracking-tight text-charcoal">
          {article.title}
        </h1>
      </header>
      <div className="space-y-3 rounded-2xl border border-charcoal/10 bg-white p-6 shadow-xs">
        {blocks.map((block, index) => {
          if (block.type === "h2") {
            return (
              <h2 key={index} className="pt-2 text-base font-semibold text-charcoal">
                {block.text}
              </h2>
            );
          }
          if (block.type === "li") {
            return (
              <p key={index} className="flex gap-2 text-sm leading-6 text-charcoal/80">
                <span aria-hidden="true" className="text-forest">•</span>
                <span>{block.text}</span>
              </p>
            );
          }
          return (
            <p key={index} className="text-sm leading-6 whitespace-pre-wrap text-charcoal/80">
              {block.text}
            </p>
          );
        })}
      </div>
    </article>
  );
}
