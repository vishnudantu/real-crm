import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Building2,
  ChevronRight,
  CreditCard,
  Gauge,
  LoaderCircle,
  PlayCircle,
  ScrollText,
  ShieldAlert,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import {
  fetchOperatorAuditLogs,
  fetchOperatorPlans,
  fetchOperatorTenants,
  updateTenantStatus,
} from "./api";
import { useOperator } from "./OperatorAuthGuard";
import { errorMessage } from "../shared/apiRequest";
import { formatDateTime, humanizeIdentifier } from "./format";
import { humanizeAction, summarizeAuditDetails } from "./operatorModel";
import type { OperatorTenant } from "./operatorModel";
import {
  ErrorBlock,
  InlineNotice,
  LoadingBlock,
  SectionHeader,
  StatusBadge,
  Surface,
  primaryButtonClasses,
  secondaryButtonClasses,
} from "./ui";

const LAST_24H_MS = 24 * 60 * 60 * 1000;

interface KpiCardProps {
  label: string;
  value: string | number;
  hint: string;
  icon: typeof Gauge;
  tone?: "default" | "danger";
  to?: string;
  loading: boolean;
}

function KpiCard({ label, value, hint, icon: Icon, tone = "default", to, loading }: KpiCardProps) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
          {label}
        </p>
        <Icon
          aria-hidden="true"
          className={`size-4 ${tone === "danger" ? "text-clay" : "text-charcoal/35"}`}
        />
      </div>
      <p
        className={`mt-2 text-2xl font-semibold tracking-tight ${
          tone === "danger" ? "text-clay" : "text-charcoal"
        }`}
      >
        {loading ? "—" : value.toLocaleString("en-IN")}
      </p>
      <p className="mt-1 text-[0.68rem] leading-4 text-charcoal/50">{hint}</p>
      {to ? (
        <span className="mt-3 inline-flex items-center gap-1 text-[0.68rem] font-semibold text-forest">
          Open view
          <ArrowUpRight aria-hidden="true" className="size-3" />
        </span>
      ) : null}
    </>
  );

  const shell = `rounded-2xl border bg-white p-4 shadow-xs transition-colors sm:p-5 ${
    tone === "danger" ? "border-clay/25" : "border-charcoal/10"
  }`;

  return to ? (
    <Link to={to} className={`${shell} group block hover:border-charcoal/25`}>
      {body}
    </Link>
  ) : (
    <div className={shell}>{body}</div>
  );
}

export function OperatorMissionControlPage() {
  const { can } = useOperator();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const tenantsQuery = useQuery({
    queryKey: ["operator", "tenants"],
    queryFn: fetchOperatorTenants,
  });
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });
  const auditQuery = useQuery({
    queryKey: ["operator", "audit-logs", { limit: 50 }],
    queryFn: () => fetchOperatorAuditLogs({ limit: 50 }),
  });

  const statusMutation = useMutation({
    mutationFn: (tenant: OperatorTenant) => updateTenantStatus(tenant.id, "active"),
    onSuccess: async (updated) => {
      setNotice({ tone: "success", text: `${updated.slug} reactivated.` });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants"] });
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: errorMessage(error, "Failed to activate the tenant.") });
    },
  });

  const stats = useMemo(() => {
    const tenants = tenantsQuery.data ?? [];
    const plans = plansQuery.data ?? [];
    const logs = auditQuery.data ?? [];
    const snapshotAt = Date.now();
    const suspended = tenants.filter((tenant) => tenant.status !== "active");
    const opsLast24h = logs.filter(
      (log) => snapshotAt - new Date(log.created_at).getTime() <= LAST_24H_MS,
    ).length;
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);
    const monthStartMs = monthStart.getTime();
    const onboardingsThisMonth = logs.filter(
      (log) =>
        log.action === "TENANT_PROVISIONED" &&
        new Date(log.created_at).getTime() >= monthStartMs,
    ).length;
    return {
      tenants,
      suspended,
      activeCount: tenants.length - suspended.length,
      plansTotal: plans.length,
      plansActive: plans.filter((plan) => plan.is_active).length,
      opsLast24h,
      onboardingsThisMonth,
      recent: logs.slice(0, 12),
    };
  }, [
    tenantsQuery.data,
    plansQuery.data,
    auditQuery.data,
  ]);

  const loading = tenantsQuery.isLoading || plansQuery.isLoading || auditQuery.isLoading;
  const failed = tenantsQuery.isError || plansQuery.isError || auditQuery.isError;

  if (failed && !tenantsQuery.data) {
    return (
      <Surface>
        <ErrorBlock
          message={[tenantsQuery, plansQuery, auditQuery]
            .map((query) =>
              query.isError && query.error instanceof Error ? query.error.message : null,
            )
            .filter((message): message is string => message !== null)
            .join(" ")}
          onRetry={() => {
            void tenantsQuery.refetch();
            void plansQuery.refetch();
            void auditQuery.refetch();
          }}
        />
      </Surface>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Mission Control
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Platform overview
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
            Live health of every tenant workspace, commercial catalog, and
            privileged operator activity across PropFlow.
          </p>
        </div>
        {can("tenants.write") ? (
          <Link to="/operator/tenants/new" className={primaryButtonClasses}>
            <WandSparkles aria-hidden="true" className="size-4" />
            Onboard tenant
          </Link>
        ) : null}
      </div>

      {notice ? <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice> : null}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Tenants"
          value={stats.tenants.length}
          hint="Workspace directories"
          icon={Building2}
          loading={loading}
          to="/operator/tenants"
        />
        <KpiCard
          label="Active"
          value={stats.activeCount}
          hint="Serving buyers today"
          icon={Gauge}
          loading={loading}
          to="/operator/tenants?status=active"
        />
        <KpiCard
          label="Suspended"
          value={stats.suspended.length}
          hint="Parked workspaces"
          icon={ShieldAlert}
          tone={stats.suspended.length > 0 ? "danger" : "default"}
          loading={loading}
          to="/operator/tenants?status=suspended"
        />
        <KpiCard
          label="Active plans"
          value={stats.plansActive}
          hint={`${stats.plansTotal} plans in catalog`}
          icon={CreditCard}
          loading={loading}
          to="/operator/plans"
        />
        <KpiCard
          label="Ops · 24h"
          value={stats.opsLast24h}
          hint="Operator actions audited"
          icon={Activity}
          loading={loading}
          to="/operator/audit-logs"
        />
        <KpiCard
          label="Onboardings · month"
          value={stats.onboardingsThisMonth}
          hint="Tenants provisioned since day 1"
          icon={Sparkles}
          loading={loading}
          to="/operator/audit-logs?action=TENANT_PROVISIONED"
        />
      </div>

      {stats.suspended.length > 0 ? (
        <section
          aria-label="Suspended tenants"
          className="rounded-2xl border border-clay/25 bg-clay-soft/50 p-5 sm:p-6"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-clay/15 text-clay">
                <ShieldAlert aria-hidden="true" className="size-5" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-charcoal">
                  {stats.suspended.length} suspended tenant{stats.suspended.length === 1 ? "" : "s"} need attention
                </h2>
                <p className="mt-0.5 text-xs text-charcoal/60">
                  Reactivate restores buyer-facing surfaces and tenant sign-in.
                </p>
              </div>
            </div>
            <Link
              to="/operator/incidents"
              className="inline-flex items-center gap-1 text-xs font-semibold text-clay hover:text-charcoal"
            >
              Incident view
              <ChevronRight aria-hidden="true" className="size-3.5" />
            </Link>
          </div>
          <ul className="mt-4 space-y-2">
            {stats.suspended.slice(0, 5).map((tenant) => (
              <li
                key={tenant.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-charcoal/10 bg-white px-4 py-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <StatusBadge status={tenant.status} />
                  <button
                    type="button"
                    onClick={() => navigate(`/operator/tenants/${tenant.id}`)}
                    className="truncate text-xs font-semibold text-charcoal hover:text-forest"
                  >
                    {tenant.brand_name}
                  </button>
                  <span className="truncate font-mono text-[0.65rem] text-charcoal/45">
                    {tenant.slug}
                  </span>
                </div>
                {can("tenants.write") ? (
                  <button
                    type="button"
                    disabled={statusMutation.isPending}
                    onClick={() => {
                      setNotice(null);
                      statusMutation.mutate(tenant);
                    }}
                    className={`${secondaryButtonClasses} min-h-9 !text-forest`}
                  >
                    {statusMutation.isPending && statusMutation.variables?.id === tenant.id ? (
                      <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
                    ) : (
                      <PlayCircle aria-hidden="true" className="size-3.5" />
                    )}
                    Activate
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <Surface>
          <SectionHeader
            eyebrow="Recent platform activity"
            title="Last audited operator actions"
            description="The twelve most recent entries in the control-plane audit trail."
            action={
              can("audit.read") ? (
                <Link
                  to="/operator/audit-logs"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-forest hover:text-forest-deep"
                >
                  <ScrollText aria-hidden="true" className="size-3.5" />
                  Audit explorer
                </Link>
              ) : null
            }
          />
          {auditQuery.isLoading ? (
            <LoadingBlock label="Loading recent activity…" />
          ) : auditQuery.isError ? (
            <ErrorBlock
              message={
                auditQuery.error instanceof Error
                  ? auditQuery.error.message
                  : "Failed to load recent activity."
              }
              onRetry={() => void auditQuery.refetch()}
            />
          ) : stats.recent.length === 0 ? (
            <div className="flex flex-col items-center px-5 py-10 text-center">
              <Activity aria-hidden="true" className="size-6 text-charcoal/35" />
              <p className="mt-3 text-sm font-semibold text-charcoal">No operator activity yet</p>
              <p className="mt-1 max-w-sm text-xs text-charcoal/55">
                Privileged changes to tenants, plans, and entitlements will
                appear here as they are made.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-charcoal/5">
              {stats.recent.map((log) => (
                <li key={log.id} className="flex items-start gap-3 px-5 py-3.5 sm:px-6">
                  <span className="mt-0.5 inline-flex shrink-0 rounded-lg border border-forest/15 bg-forest/5 px-2 py-1 text-[0.62rem] font-semibold text-forest-deep">
                    {humanizeAction(log.action)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-charcoal">
                      {log.actor_email}
                      <span className="font-normal text-charcoal/55">
                        {" "}· {humanizeIdentifier(log.resource_type)}
                      </span>
                    </p>
                    <p className="mt-0.5 truncate text-[0.68rem] text-charcoal/55">
                      {summarizeAuditDetails(log.details)}
                    </p>
                  </div>
                  <span className="shrink-0 text-right text-[0.65rem] whitespace-nowrap text-charcoal/45">
                    {formatDateTime(log.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Surface>

        <div className="space-y-5">
          <Surface>
            <SectionHeader eyebrow="Quick links" title="Jump into operations" />
            <div className="grid gap-2 p-5 sm:p-6">
              {[
                {
                  to: "/operator/tenants",
                  icon: Building2,
                  label: "Tenant directory",
                  hint: "Search, filter, open Tenant 360",
                  show: can("tenants.read"),
                },
                {
                  to: "/operator/incidents",
                  icon: ShieldAlert,
                  label: "Incidents",
                  hint: "Suspended workspaces and health checks",
                  show: can("tenants.read"),
                },
                {
                  to: "/operator/tenants/new",
                  icon: WandSparkles,
                  label: "Onboard a tenant",
                  hint: "Guided four-step wizard",
                  show: can("tenants.write"),
                },
                {
                  to: "/operator/plans",
                  icon: CreditCard,
                  label: "Plans & entitlements",
                  hint: "Pricing, limits, feature bundles",
                  show: can("tenants.read"),
                },
                {
                  to: "/operator/audit-logs",
                  icon: ScrollText,
                  label: "Audit explorer",
                  hint: "Filter privileged activity by action or tenant",
                  show: can("audit.read"),
                },
              ]
                .filter((link) => link.show)
                .map((link) => {
                  const Icon = link.icon;
                  return (
                    <Link
                      key={link.to}
                      to={link.to}
                      className="group flex items-center gap-3 rounded-xl border border-charcoal/10 bg-white px-4 py-3 transition-colors hover:border-forest/30 hover:bg-forest/[0.03]"
                    >
                      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-charcoal/5 text-charcoal/60 transition-colors group-hover:bg-forest/10 group-hover:text-forest">
                        <Icon aria-hidden="true" className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold text-charcoal">{link.label}</span>
                        <span className="block truncate text-[0.68rem] text-charcoal/50">{link.hint}</span>
                      </span>
                      <ChevronRight aria-hidden="true" className="size-4 text-charcoal/30 transition-colors group-hover:text-forest" />
                    </Link>
                  );
                })}
            </div>
          </Surface>

          <Surface>
            <SectionHeader eyebrow="Catalog snapshot" title="Commercial plans" />
            {plansQuery.isLoading ? (
              <LoadingBlock label="Loading plans…" />
            ) : (plansQuery.data ?? []).length === 0 ? (
              <p className="px-5 py-6 text-xs leading-5 text-charcoal/55 sm:px-6">
                No subscription plans exist yet. Create one under Revenue →
                Plans &amp; Entitlements to attach limits and feature bundles.
              </p>
            ) : (
              <ul className="divide-y divide-charcoal/5">
                {(plansQuery.data ?? [])
                  .slice(0, 4)
                  .map((plan) => (
                    <li key={plan.id} className="flex items-center justify-between gap-3 px-5 py-3 sm:px-6">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-charcoal">{plan.name}</p>
                        <p className="font-mono text-[0.62rem] text-charcoal/45">{plan.code}</p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[0.6rem] font-semibold uppercase ${
                          plan.is_active
                            ? "border-forest/25 bg-forest/10 text-forest-deep"
                            : "border-charcoal/15 bg-charcoal/5 text-charcoal/50"
                        }`}
                      >
                        {plan.is_active ? "Active" : "Inactive"}
                      </span>
                    </li>
                  ))}
              </ul>
            )}
          </Surface>
        </div>
      </div>
    </div>
  );
}
