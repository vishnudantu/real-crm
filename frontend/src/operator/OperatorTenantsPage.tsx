import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ChevronRight,
  Plus,
  Search,
  Users,
} from "lucide-react";
import { fetchOperatorPlans, fetchOperatorTenants } from "./api";
import { useOperator } from "./OperatorAuthGuard";
import type { TenantStatus } from "./operatorModel";
import {
  ErrorBlock,
  LoadingBlock,
  SectionHeader,
  StatusBadge,
  Surface,
  primaryButtonClasses,
  inputClasses,
} from "./ui";

const STATUS_FILTERS: { value: TenantStatus | "all"; label: string }[] = [
  { value: "all", label: "All tenants" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
];

export function OperatorTenantsPage() {
  const { can } = useOperator();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get("status");
  const status: TenantStatus | "all" =
    statusParam === "active" || statusParam === "suspended" ? statusParam : "all";
  const [search, setSearch] = useState("");

  const setStatus = (value: TenantStatus | "all") => {
    const next = new URLSearchParams(searchParams);
    if (value === "all") next.delete("status");
    else next.set("status", value);
    setSearchParams(next, { replace: true });
  };

  const tenantsQuery = useQuery({
    queryKey: ["operator", "tenants"],
    queryFn: fetchOperatorTenants,
  });
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });

  const tenants = tenantsQuery.data ?? [];
  const plans = plansQuery.data ?? [];
  const filtered = tenants.filter((tenant) => {
    const matchesSearch = `${tenant.name} ${tenant.slug} ${tenant.brand_name}`
      .toLowerCase()
      .includes(search.trim().toLowerCase());
    return matchesSearch && (status === "all" || tenant.status === status);
  });
  const activeCount = tenants.filter((tenant) => tenant.status === "active").length;
  const totalLeads = tenants.reduce((sum, tenant) => sum + tenant.leads, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Organizations
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Tenant directory
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-charcoal/60">
            Search every workspace, inspect its plan and region, and open
            Tenant 360 for configuration, entitlements, and usage.
          </p>
        </div>
        {can("tenants.write") ? (
          <Link to="/operator/tenants/new" className={primaryButtonClasses}>
            <Plus aria-hidden="true" className="size-4" />
            Provision tenant
          </Link>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[
          { label: "Total tenants", value: tenants.length },
          { label: "Active tenants", value: activeCount },
          { label: "Suspended", value: tenants.length - activeCount },
          { label: "Leads captured", value: totalLeads },
        ].map((metric) => (
          <div
            key={metric.label}
            className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs sm:p-5"
          >
            <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
              {metric.label}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-charcoal">
              {tenantsQuery.isLoading ? "—" : metric.value.toLocaleString("en-IN")}
            </p>
          </div>
        ))}
      </div>

      <Surface>
        <SectionHeader
          eyebrow="Workspace directory"
          title={`${filtered.length} of ${tenants.length} tenants`}
          description="Open a tenant for Tenant 360: health, branding, entitlements, usage, and deployments."
        />

        <div className="flex flex-col gap-3 border-b border-charcoal/10 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
          <div className="relative flex-1 sm:max-w-sm">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-charcoal/40"
            />
            <label htmlFor="tenant-search" className="sr-only">
              Search tenants
            </label>
            <input
              id="tenant-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name, brand, or slug…"
              className={`${inputClasses} mt-0 pl-10`}
            />
          </div>
          <div className="flex rounded-xl border border-charcoal/10 bg-charcoal/5 p-1">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatus(filter.value)}
                className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-colors sm:flex-none ${
                  status === filter.value
                    ? "bg-white text-charcoal shadow-xs"
                    : "text-charcoal/55 hover:text-charcoal"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        {tenantsQuery.isLoading ? (
          <LoadingBlock label="Loading tenant directory…" />
        ) : tenantsQuery.isError ? (
          <ErrorBlock
            message={
              tenantsQuery.error instanceof Error
                ? tenantsQuery.error.message
                : "Failed to load tenants."
            }
            onRetry={() => void tenantsQuery.refetch()}
          />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-12 text-center">
            <span className="grid size-11 place-items-center rounded-2xl bg-charcoal/5 text-charcoal/45">
              <Building2 aria-hidden="true" className="size-5" />
            </span>
            <p className="mt-3 text-sm font-semibold text-charcoal">
              {tenants.length === 0 ? "No tenants provisioned yet" : "No tenants match your filters"}
            </p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-charcoal/55">
              {tenants.length === 0
                ? "Provision the first tenant workspace to create its branding, subscription plan, and admin account."
                : "Try a different search term or status filter."}
            </p>
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-charcoal/10 text-[0.62rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                    <th className="px-6 py-3">Tenant</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Plan</th>
                    <th className="px-4 py-3">Users</th>
                    <th className="px-4 py-3">Leads</th>
                    <th className="px-4 py-3">Bookings</th>
                    <th className="px-4 py-3">Messages</th>
                    <th className="px-6 py-3 text-right">Region</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-charcoal/5">
                  {filtered.map((tenant) => (
                    <tr key={tenant.id} className="group transition-colors hover:bg-forest/[0.03]">
                      <td className="px-6 py-4">
                        <Link to={`/operator/tenants/${tenant.id}`} className="flex items-center gap-3">
                          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-charcoal/5 text-sm font-bold text-charcoal/65 transition-colors group-hover:bg-forest/10 group-hover:text-forest">
                            {tenant.brand_name.charAt(0).toUpperCase()}
                          </span>
                          <span className="min-w-0">
                            <span className="block font-semibold text-charcoal group-hover:text-forest">
                              {tenant.brand_name}
                            </span>
                            <span className="mt-0.5 block text-[0.65rem] text-charcoal/50">
                              {tenant.slug}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-4"><StatusBadge status={tenant.status} /></td>
                      <td className="px-4 py-4 font-medium text-charcoal/70">
                        {plans.find((plan) => plan.id === tenant.plan_id)?.name ?? "No plan"}
                      </td>
                      <td className="px-4 py-4 text-charcoal/70">{tenant.users}</td>
                      <td className="px-4 py-4 text-charcoal/70">{tenant.leads.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-4 text-charcoal/70">{tenant.bookings.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-4 text-charcoal/70">{tenant.deliveries.toLocaleString("en-IN")}</td>
                      <td className="px-6 py-4 text-right text-charcoal/55">
                        <span className="inline-flex items-center gap-2">
                          {tenant.country} · {tenant.currency}
                          <ChevronRight aria-hidden="true" className="size-3.5 text-charcoal/30" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-charcoal/10 lg:hidden">
              {filtered.map((tenant) => (
                <Link
                  key={tenant.id}
                  to={`/operator/tenants/${tenant.id}`}
                  className="block p-5 transition-colors hover:bg-forest/[0.03]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-charcoal">
                        {tenant.brand_name}
                      </p>
                      <p className="mt-0.5 text-xs text-charcoal/50">
                        {tenant.slug} · {plans.find((plan) => plan.id === tenant.plan_id)?.name ?? "No plan"}
                      </p>
                    </div>
                    <StatusBadge status={tenant.status} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-charcoal/65">
                    <span className="inline-flex items-center gap-1.5">
                      <Users aria-hidden="true" className="size-3.5 text-charcoal/40" />
                      {tenant.users} users
                    </span>
                    <span>{tenant.leads.toLocaleString("en-IN")} leads</span>
                    <span>{tenant.bookings.toLocaleString("en-IN")} bookings</span>
                    <span>{tenant.deliveries.toLocaleString("en-IN")} messages</span>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </Surface>
    </div>
  );
}
