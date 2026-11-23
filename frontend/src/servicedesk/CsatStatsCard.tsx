import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, MessageSquareHeart, RefreshCw, Smile } from "lucide-react";
import {
  saleCardClasses,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { csatKeys, fetchCsatStats } from "./serviceDeskApi";
import type { CsatPeriod, CsatStats } from "./serviceDeskModel";
import {
  CSAT_PERIODS,
  csatAverageLabel,
  csatResponseRateLabel,
} from "./serviceDeskModel";

interface CsatStatsCardProps {
  period: CsatPeriod;
  onPeriodChange: (period: CsatPeriod) => void;
}

/** Board card: average CSAT for the window + monthly opens/closes trend. */
export function CsatStatsCard({ period, onPeriodChange }: CsatStatsCardProps) {
  const query = useQuery({
    queryKey: csatKeys.stats(period),
    queryFn: () => fetchCsatStats(period),
    staleTime: 60_000,
  });

  return (
    <section
      className={`${saleCardClasses} p-5`}
      aria-label="Customer satisfaction statistics"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight text-charcoal">
          <MessageSquareHeart aria-hidden="true" className="size-4 text-emerald-600" />
          Customer satisfaction
        </h2>
        <label className="flex items-center gap-2 text-[11px] font-semibold text-charcoal/60">
          <span className="sr-only">CSAT period</span>
          <select
            value={period}
            onChange={(event) => onPeriodChange(event.target.value as CsatPeriod)}
            className="rounded-lg border border-charcoal/15 bg-white px-2 py-1 text-[11px]"
          >
            {CSAT_PERIODS.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {query.isLoading && (
        <div className="flex items-center gap-2 py-6 text-xs text-charcoal/60">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading CSAT…</span>
        </div>
      )}
      {query.isError && (
        <div className="flex items-center justify-between gap-3 py-4">
          <p className="text-xs text-rose-700">
            {errorMessage(query.error, "CSAT statistics failed to load.")}
          </p>
          <button type="button" onClick={() => void query.refetch()} className={saleSecondaryButton}>
            <RefreshCw aria-hidden="true" className="size-3.5" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {query.data && <CsatStatsBody stats={query.data} />}
    </section>
  );
}

function PeriodBadge({ period }: { period: string }) {
  return (
    <span className="rounded-full border border-charcoal/10 bg-[#FAFAF7] px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap text-charcoal/60">
      {period}
    </span>
  );
}

function CsatStatsBody({ stats }: { stats: CsatStats }) {
  const average = stats.average_rating;
  const histogram = [1, 2, 3, 4, 5].map((rating) => ({
    rating,
    count: stats.rating_histogram[String(rating)] ?? stats.rating_histogram[rating] ?? 0,
  }));
  const maxCount = Math.max(1, ...histogram.map((bucket) => bucket.count));
  return (
    <div className="mt-4 grid gap-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div className="flex flex-col justify-center rounded-xl border border-emerald-100 bg-emerald-50/50 p-4 text-center">
        <p className="flex items-center justify-center gap-1 text-2xl font-semibold text-emerald-800">
          <Smile aria-hidden="true" className="size-5" />
          {csatAverageLabel(average)}
        </p>
        <p className="mt-1 text-[11px] text-emerald-900/70">
          {stats.rated} of {stats.surveys} surveys answered ({csatResponseRateLabel(stats.response_rate)})
        </p>
        <div className="mt-3 space-y-1">
          {histogram.map((bucket) => (
            <div key={bucket.rating} className="flex items-center gap-2 text-[10px] text-charcoal/60">
              <span className="w-3 text-right font-semibold">{bucket.rating}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-charcoal/10">
                <div
                  className="h-full rounded-full bg-emerald-500"
                  style={{ width: `${(bucket.count / maxCount) * 100}%` }}
                />
              </div>
              <span className="w-5 text-left tabular-nums">{bucket.count}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-[10px] font-semibold tracking-wider text-charcoal/50 uppercase">
          Monthly CSAT &amp; ticket flow
        </h3>
        <ul className="mt-2 space-y-1.5">
          {stats.periods.length === 0 && stats.ticket_trends.length === 0 && (
            <li className="rounded-xl border border-charcoal/10 bg-white px-3 py-2.5 text-[11px] text-charcoal/55">
              No closed tickets in this window yet — CSAT appears after the first close.
            </li>
          )}
          {stats.ticket_trends.map((trend) => {
            const periodStat = stats.periods.find((entry) => entry.period === trend.period);
            return (
              <li
                key={trend.period}
                className="flex items-center justify-between gap-3 rounded-xl border border-charcoal/10 bg-white px-3 py-2 text-[11px]"
              >
                <PeriodBadge period={trend.period} />
                <span className="text-charcoal/60">
                  {trend.opened} open · {trend.closed} closed
                </span>
                <span className="font-semibold whitespace-nowrap text-charcoal/80">
                  {periodStat ? csatAverageLabel(periodStat.average_rating) : "—"}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-[10.5px] text-charcoal/50">
          {stats.unresolved_tickets} unresolved ticket{stats.unresolved_tickets === 1 ? "" : "s"} right now.
        </p>
      </div>
    </div>
  );
}
