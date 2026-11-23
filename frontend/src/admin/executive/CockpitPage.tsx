import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Building2,
  ClipboardCheck,
  Layers,
  LoaderCircle,
  ShieldAlert,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { fetchExecutiveCockpit } from "./api";
import { fetchProjects } from "../api";
import {
  collectionsTrailingSum,
  formatPaise,
  toCollectionsSeries,
  toVelocitySeries,
  trailingSum,
} from "./executiveModel";
import type { CockpitResponse, ProjectRankRow } from "./executiveModel";
import { VelocityChart } from "./VelocityChart";
import { CollectionsChart } from "./CollectionsChart";
import { BriefingPanel } from "./BriefingPanel";

interface KpiCardProps {
  label: string;
  value: string;
  hint: string;
  icon: typeof TrendingUp;
  tone?: "default" | "danger" | "warn";
  loading: boolean;
}

function KpiCard({ label, value, hint, icon: Icon, tone = "default", loading }: KpiCardProps) {
  const toneClass =
    tone === "danger" ? "text-clay" : tone === "warn" ? "text-amber-700" : "text-charcoal";
  const borderClass =
    tone === "danger" ? "border-clay/25" : tone === "warn" ? "border-amber-300/40" : "border-charcoal/10";
  return (
    <div className={`rounded-2xl border bg-white p-4 shadow-xs sm:p-5 ${borderClass}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">{label}</p>
        <Icon aria-hidden="true" className={`size-4 ${tone === "default" ? "text-charcoal/35" : toneClass}`} />
      </div>
      <p className={`mt-2 text-2xl font-semibold tracking-tight ${toneClass}`}>
        {loading ? "—" : value}
      </p>
      <p className="mt-1 text-[0.68rem] leading-4 text-charcoal/50">{hint}</p>
    </div>
  );
}

export function CockpitPage() {
  const [projectId, setProjectId] = useState<string>("");
  const [months, setMonths] = useState<number>(12);

  const projectsQuery = useQuery({
    queryKey: ["executive", "projects"],
    queryFn: () => fetchProjects({ pageSize: 100 }),
    staleTime: 1000 * 60 * 5,
  });

  const cockpitQuery = useQuery({
    queryKey: ["executive", "cockpit", projectId, months],
    queryFn: () =>
      fetchExecutiveCockpit({
        projectId: projectId || null,
        months,
      }),
    staleTime: 1000 * 30,
  });

  const data = cockpitQuery.data;
  const velocitySeries = useMemo(
    () => toVelocitySeries(data?.sales_velocity ?? []),
    [data],
  );
  const collectionsSeries = useMemo(
    () => toCollectionsSeries(data?.collections ?? []),
    [data],
  );

  const projects = projectsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Executive Cockpit
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Sales, collections & delivery at a glance
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
            A read-only roll-up across every live project: funnel velocity, cash
            collected, unsold inventory value, and the queues that need a decision.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal/75">
            <Building2 aria-hidden="true" className="size-4 text-charcoal/40" />
            <select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="rounded-xl border border-charcoal/15 bg-white px-3 py-2 text-sm text-charcoal focus:border-forest focus:outline-hidden focus:ring-4 focus:ring-forest/10"
            >
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
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
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Enquiries · 3mo"
          value={trailingSum(velocitySeries, "enquiries").toLocaleString("en-IN")}
          hint="New leads in the trailing quarter"
          icon={Activity}
          loading={cockpitQuery.isLoading}
        />
        <KpiCard
          label="Bookings · 3mo"
          value={trailingSum(velocitySeries, "bookings").toLocaleString("en-IN")}
          hint={formatPaise(trailingSum(velocitySeries, "valuePaise")) + " booked"}
          icon={TrendingUp}
          loading={cockpitQuery.isLoading}
        />
        <KpiCard
          label="Collected · 3mo"
          value={formatPaise(collectionsTrailingSum(collectionsSeries))}
          hint="Live receipts; voided entries excluded"
          icon={Wallet}
          loading={cockpitQuery.isLoading}
        />
        <KpiCard
          label="Unsold value"
          value={formatPaise(data?.inventory.unsold_value_paise ?? 0)}
          hint={`${data?.inventory.available ?? 0} available · ${data?.inventory.total_units ?? 0} units`}
          icon={Layers}
          loading={cockpitQuery.isLoading}
        />
        <KpiCard
          label="Approvals pending"
          value={String(data?.approvals.pending_count ?? 0)}
          hint={formatPaise(data?.approvals.pending_amount_paise ?? 0) + " under review"}
          icon={ClipboardCheck}
          tone={(data?.approvals.pending_count ?? 0) > 0 ? "warn" : "default"}
          loading={cockpitQuery.isLoading}
        />
        <KpiCard
          label="Overdue / SLA"
          value={`${data?.overdue_installments.count ?? 0} / ${data?.ticket_sla.breaching_count ?? 0}`}
          hint={`${formatPaise(data?.overdue_installments.amount_paise ?? 0)} overdue`}
          icon={ShieldAlert}
          tone={
            (data?.overdue_installments.count ?? 0) > 0 || (data?.ticket_sla.breaching_count ?? 0) > 0
              ? "danger"
              : "default"
          }
          loading={cockpitQuery.isLoading}
        />
      </div>

      {cockpitQuery.isError ? (
        <div role="alert" className="rounded-2xl border border-clay/25 bg-clay-soft/60 p-5 text-sm text-clay">
          <div className="flex items-start gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-semibold">Cockpit could not be loaded</p>
              <p className="mt-1 text-xs leading-5">
                {cockpitQuery.error instanceof Error ? cockpitQuery.error.message : "Unexpected error."}
              </p>
              <button
                type="button"
                onClick={() => void cockpitQuery.refetch()}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-charcoal/20 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
            <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Sales velocity</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Enquiries → visits → bookings</h2>
            <p className="mt-1 text-xs leading-5 text-charcoal/60">
              Monthly funnel across the selected window. Cancelled sale bookings are excluded from counts and value.
            </p>
          </div>
          <div className="p-5 sm:p-6">
            {cockpitQuery.isLoading ? (
              <div role="status" className="flex min-h-56 items-center justify-center gap-2 text-sm text-charcoal/60">
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                Loading sales velocity…
              </div>
            ) : (
              <VelocityChart series={velocitySeries} />
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
            <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Collections</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Cash received by month</h2>
            <p className="mt-1 text-xs leading-5 text-charcoal/60">
              Live receipts joined to their booking's project. Voided receipts never count.
            </p>
          </div>
          <div className="p-5 sm:p-6">
            {cockpitQuery.isLoading ? (
              <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-sm text-charcoal/60">
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                Loading collections…
              </div>
            ) : (
              <CollectionsChart series={collectionsSeries} />
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <ProjectRankingTable ranking={data?.project_ranking ?? []} loading={cockpitQuery.isLoading} />
        <AttentionPanel data={data} loading={cockpitQuery.isLoading} />
      </div>

      <BriefingPanel />
    </div>
  );
}

function ProjectRankingTable({ ranking, loading }: { ranking: ProjectRankRow[]; loading: boolean }) {
  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
      <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
        <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Project ranking</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Velocity leaderboard (90 days)</h2>
        <p className="mt-1 text-xs leading-5 text-charcoal/60">
          Score = bookings × 3 + completed visits × 1 + enquiries × 0.1. Ties break alphabetically.
        </p>
      </div>
      {loading ? (
        <div role="status" className="flex min-h-40 items-center justify-center gap-2 text-sm text-charcoal/60">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Ranking projects…
        </div>
      ) : ranking.length === 0 ? (
        <p className="px-5 py-8 text-center text-xs text-charcoal/55 sm:px-6">
          No projects yet. Create a project to see its velocity here.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-charcoal/10 text-charcoal/50">
                <th scope="col" className="px-5 py-3 font-semibold sm:px-6">#</th>
                <th scope="col" className="px-3 py-3 font-semibold">Project</th>
                <th scope="col" className="px-3 py-3 font-semibold">Enquiries</th>
                <th scope="col" className="px-3 py-3 font-semibold">Visits</th>
                <th scope="col" className="px-3 py-3 font-semibold">Bookings</th>
                <th scope="col" className="px-3 py-3 font-semibold">Booked</th>
                <th scope="col" className="px-3 py-3 font-semibold">Collected</th>
                <th scope="col" className="px-3 py-3 font-semibold">Unsold</th>
                <th scope="col" className="px-5 py-3 font-semibold sm:px-6">Score</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((row, index) => (
                <tr key={row.project_id} className="border-b border-charcoal/5 text-charcoal/75 last:border-0">
                  <td className="px-5 py-3 font-mono text-charcoal/45 sm:px-6">{index + 1}</td>
                  <td className="px-3 py-3 font-semibold text-charcoal">{row.project_name}</td>
                  <td className="px-3 py-3 font-mono">{row.enquiries}</td>
                  <td className="px-3 py-3 font-mono">{row.visits_completed}</td>
                  <td className="px-3 py-3 font-mono">{row.bookings}</td>
                  <td className="px-3 py-3 font-mono">{formatPaise(row.booking_value_paise)}</td>
                  <td className="px-3 py-3 font-mono">{formatPaise(row.collected_paise)}</td>
                  <td className="px-3 py-3 font-mono">{row.unsold_units}</td>
                  <td className="px-5 py-3 font-mono font-semibold text-forest-deep sm:px-6">{row.velocity_score.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AttentionPanel({ data, loading }: { data: CockpitResponse | undefined; loading: boolean }) {
  const overdue = data?.overdue_installments;
  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white shadow-xs">
      <div className="border-b border-charcoal/10 px-5 py-5 sm:px-6">
        <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">Needs attention</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">Overdue installments</h2>
        <p className="mt-1 text-xs leading-5 text-charcoal/60">
          Open installments past their due date, netted by live receipts. Oldest first.
        </p>
      </div>
      {loading ? (
        <div role="status" className="flex min-h-40 items-center justify-center gap-2 text-sm text-charcoal/60">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Loading overdue items…
        </div>
      ) : !overdue || overdue.sample.length === 0 ? (
        <p className="px-5 py-8 text-center text-xs text-charcoal/55 sm:px-6">
          Nothing overdue. Every open installment is inside its due date.
        </p>
      ) : (
        <ul className="divide-y divide-charcoal/5">
          {overdue.sample.map((row) => (
            <li key={row.installment_id} className="flex items-start justify-between gap-3 px-5 py-3 sm:px-6">
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-charcoal">
                  {row.unit_number} · {row.milestone}
                </p>
                <p className="mt-0.5 text-[0.68rem] text-charcoal/55">
                  Due {row.due_on} · {row.days_overdue} day{row.days_overdue === 1 ? "" : "s"} overdue
                </p>
              </div>
              <span className="shrink-0 inline-flex items-center gap-1 rounded-full border border-clay/25 bg-clay-soft px-2.5 py-1 text-[0.65rem] font-semibold text-clay">
                {formatPaise(row.amount_paise)}
                <ArrowUpRight aria-hidden="true" className="size-3" />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
