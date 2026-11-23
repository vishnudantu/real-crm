import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  CreditCard,
  IndianRupee,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  Users,
} from "lucide-react";
import { fetchRevenueSummary } from "./api";
import {
  formatRevenuePaise,
  meterLabel,
  renewalUrgency,
  toInvoicedSeries,
} from "./revenueModel";
import type { InvoicedSeriesPoint } from "./revenueModel";

function Kpi({ label, value, hint, icon: Icon, tone = "default", loading }: {
  label: string;
  value: string;
  hint: string;
  icon: typeof IndianRupee;
  tone?: "default" | "danger" | "warn";
  loading: boolean;
}) {
  const toneClass = tone === "danger" ? "text-clay" : tone === "warn" ? "text-amber-700" : "text-charcoal";
  const border = tone === "danger" ? "border-clay/25" : tone === "warn" ? "border-amber-300/40" : "border-charcoal/10";
  return (
    <div className={`rounded-2xl border bg-white p-4 shadow-xs sm:p-5 ${border}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">{label}</p>
        <Icon aria-hidden="true" className={`size-4 ${tone === "default" ? "text-charcoal/35" : toneClass}`} />
      </div>
      <p className={`mt-2 text-2xl font-semibold tracking-tight ${toneClass}`}>{loading ? "—" : value}</p>
      <p className="mt-1 text-[0.68rem] leading-4 text-charcoal/50">{hint}</p>
    </div>
  );
}

export function RevenuePage() {
  const [months, setMonths] = useState(6);
  const query = useQuery({
    queryKey: ["operator", "revenue", months],
    queryFn: () => fetchRevenueSummary(months),
    staleTime: 1000 * 60,
  });

  const data = query.data;
  const invoicedSeries = useMemo(() => toInvoicedSeries(data?.invoiced ?? []), [data]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">Revenue</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Revenue Command Centre
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
            Recurring revenue, invoice capture, payment failures, expansion signals and
            upcoming renewals across every tenant workspace. Read-only.
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal/75">
          <select
            value={months}
            onChange={(event) => setMonths(Number(event.target.value))}
            className="rounded-xl border border-charcoal/15 bg-white px-3 py-2 text-sm text-charcoal focus:border-forest focus:outline-hidden focus:ring-4 focus:ring-forest/10"
          >
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
            <option value={24}>Last 24 months</option>
          </select>
        </label>
      </div>

      {query.isError ? (
        <div role="alert" className="rounded-2xl border border-clay/25 bg-clay-soft/60 p-5 text-sm text-clay">
          <div className="flex items-start gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-semibold">Revenue summary unavailable</p>
              <p className="mt-1 text-xs leading-5">
                {query.error instanceof Error ? query.error.message : "Unexpected error."}
              </p>
              <button
                type="button"
                onClick={() => void query.refetch()}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-charcoal/20 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal"
              >
                <RefreshCw aria-hidden="true" className="size-3.5" />
                Try again
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-5">
        <Kpi label="MRR" value={formatRevenuePaise(data?.mrr_paise ?? 0)} hint={`${data?.active_subscriptions ?? 0} active subscriptions`} icon={IndianRupee} loading={query.isLoading} />
        <Kpi label="ARR" value={formatRevenuePaise(data?.arr_paise ?? 0)} hint="MRR annualised (×12)" icon={TrendingUp} loading={query.isLoading} />
        <Kpi label="At-risk MRR" value={formatRevenuePaise((data?.at_risk.past_due_mrr_paise ?? 0) + (data?.at_risk.halted_mrr_paise ?? 0))} hint={`${data?.at_risk.past_due_count ?? 0} past due · ${data?.at_risk.halted_count ?? 0} halted`} icon={ShieldAlert} tone={((data?.at_risk.halted_count ?? 0) + (data?.at_risk.past_due_count ?? 0)) > 0 ? "danger" : "default"} loading={query.isLoading} />
        <Kpi label="Payment failures · 30d" value={String(data?.failures.count_last_30_days ?? 0)} hint={`${data?.failures.halted_tenants ?? 0} tenants halted`} icon={CreditCard} tone={(data?.failures.count_last_30_days ?? 0) > 0 ? "warn" : "default"} loading={query.isLoading} />
        <Kpi label="Renewals · 30d" value={String(data?.renewals.count ?? 0)} hint={`${formatRevenuePaise(data?.renewals.mrr_at_stake_paise ?? 0)} MRR renewing`} icon={Users} loading={query.isLoading} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
            <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Invoiced revenue</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Captured payments by month</h2>
            <p className="mt-1 text-xs leading-5 text-charcoal/60">
              Paid invoices only (distinct from the MRR plan-price snapshot). Draft invoices excluded.
            </p>
          </div>
          <div className="p-5 sm:p-6">
            {query.isLoading ? (
              <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-sm text-charcoal/60">
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                Loading invoiced revenue…
              </div>
            ) : (
              <InvoicedChart series={invoicedSeries} />
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
            <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Expansion signals</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Tenants nearing plan limits</h2>
            <p className="mt-1 text-xs leading-5 text-charcoal/60">
              Any usage meter at ≥80% of its plan limit is an upsell conversation.
            </p>
          </div>
          {query.isLoading ? (
            <div role="status" className="flex min-h-40 items-center justify-center gap-2 text-sm text-charcoal/60">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              Loading signals…
            </div>
          ) : (data?.expansion_signals.length ?? 0) === 0 ? (
            <p className="px-5 py-8 text-center text-xs text-charcoal/55 sm:px-6">
              No tenant is above 80% of a plan limit right now.
            </p>
          ) : (
            <ul className="divide-y divide-charcoal/5">
              {data!.expansion_signals.map((signal) => (
                <li key={`${signal.tenant_id}-${signal.meter}`} className="px-5 py-3 sm:px-6">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <Link to={`/operator/tenants/${signal.tenant_id}`} className="truncate text-xs font-semibold text-charcoal hover:text-forest">
                        {signal.tenant_name}
                      </Link>
                      <p className="mt-0.5 text-[0.68rem] text-charcoal/55">
                        {meterLabel(signal.meter)} · {signal.used.toLocaleString("en-IN")} of {signal.limit.toLocaleString("en-IN")}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[0.62rem] font-semibold ${signal.ratio >= 0.95 ? "border-clay/25 bg-clay-soft text-clay" : "border-amber-300/40 bg-amber-50 text-amber-800"}`}>
                      {Math.round(signal.ratio * 100)}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-charcoal/5">
                    <div
                      className={`h-full rounded-full ${signal.ratio >= 0.95 ? "bg-clay" : "bg-amber-500"}`}
                      style={{ width: `${Math.min(100, Math.max(2, signal.ratio * 100))}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
        <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
          <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Renewals due · next 30 days</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Upcoming subscription renewals</h2>
        </div>
        {query.isLoading ? (
          <div role="status" className="flex min-h-32 items-center justify-center gap-2 text-sm text-charcoal/60">
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            Loading renewals…
          </div>
        ) : (data?.renewals.subscriptions.length ?? 0) === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-charcoal/55 sm:px-6">
            No active subscriptions renew in the next 30 days.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-charcoal/10 text-charcoal/50">
                  <th scope="col" className="px-5 py-3 font-semibold sm:px-6">Tenant</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Plan</th>
                  <th scope="col" className="px-3 py-3 font-semibold">Period ends</th>
                  <th scope="col" className="px-3 py-3 font-semibold">In</th>
                  <th scope="col" className="px-5 py-3 font-semibold sm:px-6">MRR</th>
                </tr>
              </thead>
              <tbody>
                {data!.renewals.subscriptions.map((row) => {
                  const urgency = renewalUrgency(row.days_until);
                  return (
                    <tr key={row.tenant_id} className="border-b border-charcoal/5 text-charcoal/75 last:border-0">
                      <td className="px-5 py-3 sm:px-6">
                        <Link to={`/operator/tenants/${row.tenant_id}`} className="font-semibold text-charcoal hover:text-forest">
                          {row.tenant_name}
                        </Link>
                        <span className="ml-2 font-mono text-[0.65rem] text-charcoal/45">{row.tenant_slug}</span>
                      </td>
                      <td className="px-3 py-3">{row.plan_name}</td>
                      <td className="px-3 py-3 font-mono">{row.period_end}</td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.62rem] font-semibold ${
                          urgency === "overdue" ? "border-clay/25 bg-clay-soft text-clay"
                          : urgency === "soon" ? "border-amber-300/40 bg-amber-50 text-amber-800"
                          : "border-charcoal/15 bg-charcoal/5 text-charcoal/60"
                        }`}>
                          {row.days_until === 0 ? "today" : `${row.days_until}d`}
                          <ArrowUpRight aria-hidden="true" className="size-3" />
                        </span>
                      </td>
                      <td className="px-5 py-3 font-mono sm:px-6">{formatRevenuePaise(row.price_paise)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function InvoicedChart({ series }: { series: InvoicedSeriesPoint[] }) {
  const [hovered, setHovered] = useState<number | null>(null);

  const { max, ticks } = useMemo(() => {
    const rawMax = series.reduce((acc, p) => Math.max(acc, p.invoicedPaise), 0);
    if (rawMax === 0) return { max: 4, ticks: [0, 1, 2, 3, 4] };
    const magnitude = 10 ** Math.floor(Math.log10(rawMax));
    const step = magnitude / 2;
    const max = Math.ceil(rawMax / step) * step;
    const ticks: number[] = [];
    for (let v = 0; v <= max; v += step) ticks.push(v);
    return { max, ticks };
  }, [series]);

  const total = series.reduce((acc, p) => acc + p.invoicedPaise, 0);
  if (series.length === 0 || total === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-charcoal/20 bg-[#FAFAF7] p-6 text-center">
        <p className="text-sm font-semibold text-charcoal">No invoiced revenue in this window</p>
        <p className="mt-1 text-xs text-charcoal/55">Paid invoices chart here once payments are captured.</p>
      </div>
    );
  }

  const CHART_HEIGHT = 200;
  const PADDING_LEFT = 56;
  const PADDING_RIGHT = 12;
  const PADDING_TOP = 14;
  const PADDING_BOTTOM = 28;
  const width = Math.max(520, series.length * 52);
  const innerWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const innerHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const baseY = PADDING_TOP + innerHeight;
  const slot = innerWidth / series.length;
  const barWidth = Math.max(10, Math.min(28, slot * 0.5));
  const yFor = (value: number) => baseY - (value / max) * innerHeight;
  const hoveredPoint = hovered !== null ? series[hovered] : null;

  return (
    <div>
      {hoveredPoint ? (
        <div className="mb-3 inline-flex flex-wrap items-center gap-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7] px-3.5 py-2 text-[0.68rem]">
          <span className="font-semibold text-charcoal">{hoveredPoint.label}</span>
          <span className="text-charcoal/70">
            Invoiced <strong className="font-mono text-charcoal">{formatRevenuePaise(hoveredPoint.invoicedPaise)}</strong>
          </span>
          <span className="text-charcoal/60">{hoveredPoint.invoices} invoice{hoveredPoint.invoices === 1 ? "" : "s"}</span>
        </div>
      ) : null}
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          width={width}
          height={CHART_HEIGHT}
          role="img"
          aria-label={`Invoiced revenue per month for the last ${series.length} months`}
          onMouseLeave={() => setHovered(null)}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={PADDING_LEFT} y1={yFor(tick)} x2={width - PADDING_RIGHT} y2={yFor(tick)} stroke="#202923" strokeOpacity={tick === 0 ? 0.18 : 0.07} strokeDasharray={tick === 0 ? undefined : "3 4"} />
              <text x={PADDING_LEFT - 6} y={yFor(tick) + 3} textAnchor="end" fontSize="9" fill="#202923" fillOpacity="0.45">{formatRevenuePaise(tick)}</text>
            </g>
          ))}
          {series.map((point, index) => {
            const x = PADDING_LEFT + index * slot + slot / 2;
            const isHovered = hovered === index;
            const height = Math.max(point.invoicedPaise > 0 ? 2 : 0, baseY - yFor(point.invoicedPaise));
            return (
              <g key={point.month} onMouseEnter={() => setHovered(index)} onTouchStart={() => setHovered(index)}>
                <rect x={PADDING_LEFT + index * slot} y={PADDING_TOP} width={slot} height={innerHeight} fill="transparent" className="cursor-crosshair" />
                <rect x={x - barWidth / 2} y={yFor(point.invoicedPaise)} width={barWidth} height={height} rx={4} fill="#2F5240" fillOpacity={isHovered ? 1 : 0.9} />
                <text x={x} y={baseY + 14} textAnchor="middle" fontSize="9" fill="#202923" fillOpacity="0.5">{point.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 flex items-center gap-4 text-[0.65rem] text-charcoal/55">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-[#2F5240]" /> Invoiced (paid)
        </span>
      </div>
      <details className="mt-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7]">
        <summary className="cursor-pointer px-4 py-2 text-xs font-semibold text-charcoal/70">View as table</summary>
        <div className="overflow-x-auto px-4 pb-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-charcoal/50">
                <th scope="col" className="py-1.5 pr-3 font-semibold">Month</th>
                <th scope="col" className="py-1.5 pr-3 font-semibold">Invoiced</th>
                <th scope="col" className="py-1.5 font-semibold">Invoices</th>
              </tr>
            </thead>
            <tbody>
              {series.map((point) => (
                <tr key={point.month} className="border-t border-charcoal/5 text-charcoal/75">
                  <td className="py-1.5 pr-3 font-medium text-charcoal">{point.label}</td>
                  <td className="py-1.5 pr-3 font-mono">{formatRevenuePaise(point.invoicedPaise)}</td>
                  <td className="py-1.5 font-mono">{point.invoices}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
