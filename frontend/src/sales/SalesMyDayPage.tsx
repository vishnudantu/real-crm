import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, CheckCircle2, ClipboardCheck, Info, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchMyDay, type MyDayItem } from "../salesFloor/api";
import { groupByUrgency, URGENCY_LABELS } from "../salesFloor/model";
import { EmptyState, ErrorState, LoadingState, Panel } from "./ui";

const TONES = {
  OVERDUE: "border-clay/25 bg-clay-soft/50 text-clay",
  DUE_TODAY: "border-forest/25 bg-forest/10 text-forest-deep",
  AGING_SILENCE: "border-sand/60 bg-sand/20 text-charcoal",
  PENDING_APPROVAL: "border-charcoal/15 bg-charcoal/5 text-charcoal/75",
};

function ChecklistItem({ item }: { item: MyDayItem }) {
  return (
    <li id={`work-${item.kind}-${item.id}`}>
      <Link
        to={item.link}
        className="group flex items-start gap-3 px-5 py-4 transition-colors hover:bg-ivory sm:px-6"
      >
        <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md border border-charcoal/20 bg-white text-transparent group-hover:border-forest" aria-hidden="true">
          <ClipboardCheck className="size-3.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-charcoal">{item.title}</span>
          <span className="mt-1 block text-xs leading-5 text-charcoal/70">{item.reason}</span>
          <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.68rem] text-charcoal/60">
            {item.project_name && <span>{item.project_name}</span>}
            <span>{item.waiting_hours.toFixed(1)}h since recorded timestamp</span>
            <span>Priority {item.priority_score}</span>
          </span>
        </span>
        <ArrowUpRight aria-hidden="true" className="mt-1 size-4 shrink-0 text-charcoal/35 transition-colors group-hover:text-forest" />
      </Link>
    </li>
  );
}

export function SalesMyDayPage() {
  const query = useQuery({ queryKey: ["sales-floor", "my-day"], queryFn: fetchMyDay, refetchInterval: 60_000 });
  const groups = groupByUrgency(query.data?.items ?? []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 pb-12">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.66rem] font-bold tracking-[0.2em] text-forest uppercase">Sales workspace</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">My Day</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/70">A prioritized checklist from your follow-ups, assigned leads, visits, conversations and approval requests.</p>
        </div>
        <button type="button" onClick={() => void query.refetch()} aria-label="Refresh my day" className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-charcoal/15 bg-white px-3 text-xs font-semibold hover:border-forest hover:text-forest">
          <RotateCw aria-hidden="true" className="size-3.5" /> Refresh
        </button>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(["OVERDUE", "DUE_TODAY", "AGING_SILENCE", "PENDING_APPROVAL"] as const).map((urgency) => (
          <div key={urgency} className={`rounded-xl border p-4 ${TONES[urgency]}`}>
            <p className="text-[0.66rem] font-semibold tracking-wider uppercase">{URGENCY_LABELS[urgency]}</p>
            <p className="mt-2 text-2xl font-semibold">{query.data?.items.filter((item) => item.urgency === urgency).length ?? 0}</p>
          </div>
        ))}
      </div>

      {query.data && (
        <aside className="flex items-start gap-2 rounded-xl border border-charcoal/10 bg-white/70 px-4 py-3 text-xs leading-5 text-charcoal/70">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-forest" />
          <p>{query.data.priority_explanation}</p>
        </aside>
      )}

      {query.isLoading ? <Panel><LoadingState label="Loading today's prioritized work" rows={5} /></Panel>
        : query.isError ? <Panel><ErrorState message={query.error instanceof Error ? query.error.message : "Could not load today's work."} onRetry={() => void query.refetch()} /></Panel>
          : groups.length === 0 ? <Panel><EmptyState icon={CheckCircle2} title="Today's checklist is clear" description="No overdue follow-ups, today's visits, aging replies or pending approvals are recorded right now." /></Panel>
            : groups.map((group) => (
              <Panel key={group.urgency} labelledBy={`group-${group.urgency}`}>
                <div className="flex items-center justify-between border-b border-charcoal/10 px-5 py-3 sm:px-6">
                  <h2 id={`group-${group.urgency}`} className="text-sm font-semibold">{group.label}</h2>
                  <span className="text-xs font-medium text-charcoal/60">{group.items.length} open</span>
                </div>
                <ul className="divide-y divide-charcoal/10">{group.items.map((item) => <ChecklistItem key={`${item.kind}-${item.id}`} item={item} />)}</ul>
              </Panel>
            ))}
    </div>
  );
}
