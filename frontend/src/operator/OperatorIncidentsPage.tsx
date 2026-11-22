import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  HeartPulse,
  LoaderCircle,
  PlayCircle,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { fetchOperatorTenants, fetchTenantHealth, updateTenantStatus } from "./api";
import { useOperator } from "./OperatorAuthGuard";
import { errorMessage } from "../shared/apiRequest";
import { healthWorstColor } from "./operatorModel";
import type { OperatorTenant } from "./operatorModel";
import {
  ErrorBlock,
  HealthChip,
  InlineNotice,
  LoadingBlock,
  SectionHeader,
  StatusBadge,
  Surface,
  secondaryButtonClasses,
} from "./ui";

interface IncidentRowProps {
  tenant: OperatorTenant;
  inspecting: boolean;
  onToggleInspect: () => void;
  canWrite: boolean;
  onActivated: (message: string) => void;
  onError: (message: string) => void;
}

/** Health is fetched only when an operator expands a row — never list-wide. */
function IncidentRow({
  tenant,
  inspecting,
  onToggleInspect,
  canWrite,
  onActivated,
  onError,
}: IncidentRowProps) {
  const queryClient = useQueryClient();
  const healthQuery = useQuery({
    queryKey: ["operator", "tenants", tenant.id, "health"],
    queryFn: () => fetchTenantHealth(tenant.id),
    enabled: inspecting,
  });
  const activateMutation = useMutation({
    mutationFn: () => updateTenantStatus(tenant.id, "active"),
    onSuccess: async (updated) => {
      onActivated(`${updated.slug} reactivated.`);
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants"] });
    },
    onError: (error: unknown) => {
      onError(errorMessage(error, `Failed to activate ${tenant.slug}.`));
    },
  });

  const checks = healthQuery.data?.checks ?? [];
  const overall = healthWorstColor(checks.map((check) => check.state));

  return (
    <li className="border-b border-charcoal/5 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <StatusBadge status={tenant.status} />
          <Link
            to={`/operator/tenants/${tenant.id}`}
            className="min-w-0 truncate text-xs font-semibold text-charcoal hover:text-forest"
          >
            {tenant.brand_name}
          </Link>
          <span className="hidden truncate font-mono text-[0.65rem] text-charcoal/45 sm:inline">
            {tenant.slug}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {canWrite && tenant.status !== "active" ? (
            <button
              type="button"
              disabled={activateMutation.isPending}
              onClick={() => activateMutation.mutate()}
              className={`${secondaryButtonClasses} min-h-9`}
            >
              {activateMutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <PlayCircle aria-hidden="true" className="size-3.5" />
              )}
              Activate
            </button>
          ) : null}
          <button
            type="button"
            onClick={onToggleInspect}
            aria-expanded={inspecting}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-charcoal/10 px-2.5 text-[0.68rem] font-semibold text-charcoal/65 transition-colors hover:bg-charcoal/5"
          >
            <HeartPulse aria-hidden="true" className="size-3.5" />
            {inspecting ? "Hide health" : "Check health"}
            <ChevronDown
              aria-hidden="true"
              className={`size-3 transition-transform ${inspecting ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      </div>

      {inspecting ? (
        <div className="border-t border-charcoal/5 bg-[#FAFAF7]/70 px-5 py-4 sm:px-6">
          {healthQuery.isLoading ? (
            <p className="flex items-center gap-2 text-xs text-charcoal/60">
              <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              Running health checks for {tenant.slug}…
            </p>
          ) : healthQuery.isError ? (
            <p className="text-xs text-clay">
              {healthQuery.error instanceof Error
                ? healthQuery.error.message
                : "Health check failed."}
            </p>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                  Overall
                </p>
                <HealthChip state={overall} />
              </div>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {checks.map((check) => (
                  <li
                    key={check.name}
                    className="flex items-start justify-between gap-3 rounded-xl border border-charcoal/10 bg-white px-3.5 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-[0.68rem] font-semibold text-charcoal">
                        {check.name.replaceAll("_", " ")}
                      </p>
                      <p className="mt-0.5 text-[0.62rem] leading-4 text-charcoal/55">{check.detail}</p>
                    </div>
                    <HealthChip state={check.state} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : null}
    </li>
  );
}

export function OperatorIncidentsPage() {
  const { can } = useOperator();
  const navigate = useNavigate();
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const tenantsQuery = useQuery({
    queryKey: ["operator", "tenants"],
    queryFn: fetchOperatorTenants,
  });

  const tenants = tenantsQuery.data ?? [];
  const suspended = tenants.filter((tenant) => tenant.status !== "active");
  const rows = showAll ? tenants : suspended;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
          Mission Control
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
          Incidents
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
          Workspaces that are suspended or otherwise off the air. Health probes
          run per tenant — open a row to inspect its checks.
        </p>
      </div>

      {notice ? <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:max-w-3xl lg:gap-4">
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className={`rounded-2xl border p-4 text-left shadow-xs transition-colors sm:p-5 ${
            !showAll
              ? "border-clay/40 bg-clay-soft"
              : "border-charcoal/10 bg-white hover:border-charcoal/25"
          }`}
        >
          <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
            Suspended
          </p>
          <p className="mt-2 text-2xl font-semibold text-clay">
            {tenantsQuery.isLoading ? "—" : suspended.length}
          </p>
        </button>
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className={`rounded-2xl border p-4 text-left shadow-xs transition-colors sm:p-5 ${
            showAll
              ? "border-charcoal/30 bg-white"
              : "border-charcoal/10 bg-white hover:border-charcoal/25"
          }`}
        >
          <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
            All tenants
          </p>
          <p className="mt-2 text-2xl font-semibold text-charcoal">
            {tenantsQuery.isLoading ? "—" : tenants.length}
          </p>
        </button>
        <button
          type="button"
          onClick={() => navigate("/operator/audit-logs?resource_type=TENANT")}
          className="rounded-2xl border border-charcoal/10 bg-white p-4 text-left shadow-xs transition-colors hover:border-charcoal/25 sm:p-5"
        >
          <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
            Tenant audit
          </p>
          <p className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-forest">
            Open explorer
            <ChevronRight aria-hidden="true" className="size-4" />
          </p>
        </button>
      </div>

      <Surface>
        <SectionHeader
          eyebrow={showAll ? "All workspaces" : "Active incidents"}
          title={
            showAll
              ? `${tenants.length} tenants on the platform`
              : `${suspended.length} suspended tenant${suspended.length === 1 ? "" : "s"}`
          }
          description={
            showAll
              ? "Expand any tenant to probe its health. Suspension is the only status the list knows without a per-tenant call."
              : "Suspended workspaces stop serving buyers. Reactivate requires tenants.write and is audited."
          }
        />

        {tenantsQuery.isLoading ? (
          <LoadingBlock label="Loading tenant statuses…" />
        ) : tenantsQuery.isError ? (
          <ErrorBlock
            message={
              tenantsQuery.error instanceof Error
                ? tenantsQuery.error.message
                : "Failed to load tenants."
            }
            onRetry={() => void tenantsQuery.refetch()}
          />
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-12 text-center">
            <span className="grid size-11 place-items-center rounded-2xl bg-forest/10 text-forest">
              <ShieldCheck aria-hidden="true" className="size-5" />
            </span>
            <p className="mt-3 text-sm font-semibold text-charcoal">No incidents open</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-charcoal/55">
              Every tenant workspace is active. Switch to “All tenants” to probe
              health on demand.
            </p>
          </div>
        ) : (
          <>
            <ul>
              {rows.map((tenant) => (
                <IncidentRow
                  key={tenant.id}
                  tenant={tenant}
                  inspecting={expandedId === tenant.id}
                  onToggleInspect={() =>
                    setExpandedId((previous) => (previous === tenant.id ? null : tenant.id))
                  }
                  canWrite={can("tenants.write")}
                  onActivated={(text) => setNotice({ tone: "success", text })}
                  onError={(text) => setNotice({ tone: "error", text })}
                />
              ))}
            </ul>
            <div className="flex items-center justify-between gap-3 px-5 py-4 sm:px-6">
              <button
                type="button"
                onClick={() => setShowAll((previous) => !previous)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-forest hover:text-forest-deep"
              >
                <ShieldAlert aria-hidden="true" className="size-3.5" />
                {showAll ? "Show suspended only" : `Probe all ${tenants.length} tenants`}
              </button>
              <p className="text-[0.65rem] text-charcoal/45">
                One health probe at a time · results are cached per tenant
              </p>
            </div>
          </>
        )}
      </Surface>
    </div>
  );
}
