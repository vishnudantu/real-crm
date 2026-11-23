import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, LoaderCircle, Newspaper } from "lucide-react";
import { fetchExecutiveBriefing } from "./api";
import { formatPaise } from "./executiveModel";

function todayInputValue(): string {
  return new Date().toISOString().slice(0, 10);
}

function yesterdayInputValue(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

export function BriefingPanel() {
  const [date, setDate] = useState<string>(yesterdayInputValue());

  const query = useQuery({
    queryKey: ["executive", "briefing", date],
    queryFn: () => fetchExecutiveBriefing(date || undefined),
    staleTime: 1000 * 60,
  });

  const data = query.data;

  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
      <div className="flex flex-col gap-3 border-b border-charcoal/10 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-1.5 text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">
            <Newspaper aria-hidden="true" className="size-3.5" />
            Morning briefing
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">
            Deterministic daily digest
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-charcoal/60">
            Yesterday's facts and open items, rendered from SQL counts with fixed
            templates. No AI summarisation — the same date always returns the same lines.
          </p>
        </div>
        <label className="inline-flex shrink-0 items-center gap-2 text-xs font-semibold text-charcoal/75">
          <CalendarDays aria-hidden="true" className="size-4 text-charcoal/45" />
          <input
            type="date"
            value={date}
            max={todayInputValue()}
            onChange={(event) => setDate(event.target.value)}
            className="rounded-xl border border-charcoal/15 bg-white px-3 py-2 text-sm text-charcoal focus:border-forest focus:outline-hidden focus:ring-4 focus:ring-forest/10"
          />
        </label>
      </div>

      {query.isLoading ? (
        <div role="status" className="flex min-h-40 items-center justify-center gap-2 px-5 py-8 text-sm text-charcoal/60">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Preparing the briefing…
        </div>
      ) : query.isError ? (
        <div role="alert" className="p-5 sm:p-6">
          <div className="rounded-xl border border-clay/25 bg-clay-soft/60 p-4 text-sm text-clay">
            <p className="font-semibold">Briefing unavailable</p>
            <p className="mt-1 text-xs leading-5">
              {query.error instanceof Error ? query.error.message : "Could not load the briefing."}
            </p>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-charcoal/20 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal"
            >
              Try again
            </button>
          </div>
        </div>
      ) : data ? (
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="text-xs font-semibold tracking-wider text-charcoal/50 uppercase">
              {data.briefing_date}
            </p>
            <ol className="mt-3 space-y-2.5">
              {data.lines.map((line, index) => (
                <li key={index} className="flex items-start gap-2.5 text-sm leading-6 text-charcoal/80">
                  <span aria-hidden="true" className="mt-2.5 size-1.5 shrink-0 rounded-full bg-forest/60" />
                  <span>{line}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="grid grid-cols-2 gap-3 self-start sm:grid-cols-3 lg:grid-cols-2">
            <BriefingStat label="New enquiries" value={String(data.counts.leads)} />
            <BriefingStat label="Visits completed" value={String(data.counts.visits_completed)} />
            <BriefingStat label="Sale bookings" value={String(data.counts.sale_bookings)} />
            <BriefingStat label="Collections" value={formatPaise(data.counts.receipts_paise)} />
            <BriefingStat label="Approvals pending" value={String(data.open_items.approvals_pending)} tone={data.open_items.approvals_pending > 0 ? "warn" : "default"} />
            <BriefingStat label="SLA breaches" value={String(data.open_items.tickets_breaching_sla)} tone={data.open_items.tickets_breaching_sla > 0 ? "danger" : "default"} />
            <BriefingStat label="Overdue installments" value={String(data.open_items.overdue_installments)} tone={data.open_items.overdue_installments > 0 ? "danger" : "default"} />
            <BriefingStat label="Overdue amount" value={formatPaise(data.open_items.overdue_amount_paise)} />
            <BriefingStat label="Unassigned leads" value={String(data.open_items.unassigned_active_leads)} tone={data.open_items.unassigned_active_leads > 0 ? "warn" : "default"} />
            <BriefingStat label="Active bookings" value={String(data.open_items.active_sale_bookings)} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function BriefingStat({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "warn" | "danger" }) {
  const toneClass =
    tone === "danger" ? "text-clay" : tone === "warn" ? "text-amber-700" : "text-charcoal";
  return (
    <div className="rounded-xl border border-charcoal/10 bg-[#FAFAF7] p-3">
      <p className="text-[0.62rem] font-semibold tracking-wider text-charcoal/50 uppercase">{label}</p>
      <p className={`mt-1.5 text-lg font-semibold tracking-tight ${toneClass}`}>{value}</p>
    </div>
  );
}
