import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, CalendarCheck, CircleDollarSign, RotateCw, UserRoundPlus, Users } from "lucide-react";
import { fetchWarRoom, type FunnelCounts } from "../salesFloor/api";
import { dailyDelta, funnelRatio } from "../salesFloor/model";
import { ErrorState, LoadingState, sourceLabel } from "../sales/ui";

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: typeof Activity }) {
  return <article className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"><div className="flex items-center justify-between gap-3"><p className="text-[0.66rem] font-semibold tracking-wider text-charcoal/60 uppercase">{label}</p><Icon aria-hidden="true" className="size-4 text-forest" /></div><p className="mt-3 text-3xl font-semibold tracking-tight text-charcoal">{value}</p></article>;
}

function Comparison({ today, average }: { today: number; average: number }) {
  const delta = dailyDelta(today, average);
  return <span className="text-xs text-charcoal/65"><strong className={delta < 0 ? "text-clay" : "text-forest"}>{delta > 0 ? "+" : ""}{delta}%</strong> vs 7-day daily average ({average})</span>;
}

export function WarRoomPage() {
  const query = useQuery({ queryKey: ["sales-floor", "war-room"], queryFn: fetchWarRoom, refetchInterval: 60_000 });
  const data = query.data;
  return <div className="mx-auto w-full max-w-[1500px] space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-[0.66rem] font-bold tracking-[0.2em] text-forest uppercase">Manager workspace</p><h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Sales War Room</h1><p className="mt-2 text-sm text-charcoal/65">Today's team activity and project funnels, compared with a seven-day daily average. UTC dates; cancelled visits excluded.</p></div>
      <button type="button" onClick={() => void query.refetch()} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-charcoal/15 bg-white px-3 text-xs font-semibold hover:border-forest hover:text-forest"><RotateCw aria-hidden="true" className="size-3.5" /> Refresh</button>
    </header>

    {query.isLoading ? <div className="rounded-2xl border border-charcoal/10 bg-white"><LoadingState label="Loading the sales war room" rows={5} /></div>
      : query.isError ? <div className="rounded-2xl border border-charcoal/10 bg-white"><ErrorState message={query.error instanceof Error ? query.error.message : "Could not load the war room."} onRetry={() => void query.refetch()} /></div>
        : data && <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Metric label="New enquiries" value={data.new_leads_total} icon={UserRoundPlus} />
            <Metric label="Visits today" value={data.visits_today} icon={CalendarCheck} />
            <Metric label="Bookings created" value={data.bookings_created_today} icon={Activity} />
            <Metric label="Unassigned leads" value={data.unassigned_leads_count} icon={Users} />
            <Metric label="Discount approvals" value={data.pending_discount_approvals} icon={CircleDollarSign} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <section aria-labelledby="team-activity" className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white">
              <div className="border-b border-charcoal/10 px-5 py-4"><h2 id="team-activity" className="font-semibold">Team activity today</h2><p className="mt-1 text-xs text-charcoal/60">Visits by slot time; bookings and assigned new leads by creation date.</p></div>
              <div className="overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm"><thead className="bg-ivory text-[0.65rem] tracking-wider text-charcoal/60 uppercase"><tr><th className="px-5 py-3 font-semibold">Executive</th><th className="px-5 py-3 font-semibold">Visits</th><th className="px-5 py-3 font-semibold">New leads</th><th className="px-5 py-3 font-semibold">Bookings</th></tr></thead><tbody className="divide-y divide-charcoal/10">{data.executive_activity.map((executive) => <tr key={executive.executive_id}><th scope="row" className="px-5 py-4 font-medium">{executive.full_name}</th><td className="px-5 py-4">{executive.visits_today}</td><td className="px-5 py-4">{executive.new_leads}</td><td className="px-5 py-4">{executive.bookings_created}</td></tr>)}</tbody></table>{data.executive_activity.length === 0 && <p className="p-5 text-sm text-charcoal/65">No active sales executives are recorded.</p>}</div>
            </section>
            <section aria-labelledby="lead-sources" className="rounded-2xl border border-charcoal/10 bg-white p-5"><h2 id="lead-sources" className="font-semibold">New leads by source</h2><ul className="mt-4 space-y-3">{data.new_leads_by_source.map((source) => <li key={source.source} className="flex items-center gap-3 text-sm"><span className="flex-1">{sourceLabel(source.source)}</span><span className="w-8 text-right font-semibold">{source.count}</span><span className="h-2 w-24 overflow-hidden rounded-full bg-charcoal/10"><span className="block h-full rounded-full bg-forest" style={{ width: `${data.new_leads_total ? source.count / data.new_leads_total * 100 : 0}%` }} /></span></li>)}</ul>{data.new_leads_by_source.length === 0 && <p className="mt-4 text-sm text-charcoal/65">No new enquiries today.</p>}</section>
          </div>

          <section aria-labelledby="project-funnels" className="space-y-4"><div><h2 id="project-funnels" className="text-lg font-semibold">Project enquiry → visit → booking funnels</h2><p className="mt-1 text-xs text-charcoal/60">Each column is a daily event count, not a conversion cohort. Projects appear when they have activity in the comparison window.</p></div><div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">{data.project_funnels.map((funnel) => <article key={funnel.project_id} className="rounded-2xl border border-charcoal/10 bg-white p-5"><div className="flex items-start justify-between gap-3"><h3 className="font-semibold">{funnel.project_name}</h3><span className="rounded-full bg-forest/10 px-2 py-1 text-[0.65rem] font-semibold text-forest">{funnelRatio(funnel.today)}% bookings / enquiries</span></div><dl className="mt-5 grid grid-cols-3 gap-2">{(["enquiries", "visits", "bookings"] as const).map((key: keyof FunnelCounts) => <div key={key}><dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/60 uppercase">{key}</dt><dd className="mt-1 text-2xl font-semibold">{funnel.today[key]}</dd><dd className="mt-2"><Comparison today={funnel.today[key]} average={funnel.seven_day_average[key]} /></dd></div>)}</dl></article>)}</div>{data.project_funnels.length === 0 && <div className="flex items-center gap-2 rounded-xl border border-charcoal/10 bg-white p-5 text-sm text-charcoal/65"><AlertCircle className="size-4 text-forest" /> No project activity recorded in the comparison window.</div>}</section>
        </>}
  </div>;
}
