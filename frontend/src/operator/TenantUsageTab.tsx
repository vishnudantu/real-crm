import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CalendarDays, MessageSquareText, Users } from "lucide-react";
import { fetchTenantUsage } from "./api";
import { usageCardData, usagePeriodLabel } from "./operatorModel";
import { TenantUsageChart } from "./TenantUsageChart";
import { ErrorBlock, LoadingBlock, MeterBar, SectionHeader, Surface } from "./ui";

interface TenantUsageTabProps {
  tenantId: string;
}

const DAY_OPTIONS = [7, 30, 90] as const;

export function TenantUsageTab({ tenantId }: TenantUsageTabProps) {
  const [days, setDays] = useState<number>(30);
  const usageQuery = useQuery({
    queryKey: ["operator", "tenants", tenantId, "usage", days],
    queryFn: () => fetchTenantUsage(tenantId, days),
    enabled: Boolean(tenantId),
  });

  if (usageQuery.isLoading) {
    return <LoadingBlock label="Loading usage meters…" />;
  }
  if (usageQuery.isError) {
    return (
      <ErrorBlock
        message={
          usageQuery.error instanceof Error
            ? usageQuery.error.message
            : "Failed to load tenant usage."
        }
        onRetry={() => void usageQuery.refetch()}
      />
    );
  }

  const usage = usageQuery.data;
  if (!usage) return null;

  const meters = usageCardData(usage.meters);

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-3">
        {meters.map((meter) => (
          <div key={meter.key} className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
            <div className="flex items-start justify-between gap-3">
              <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                {meter.label}
              </p>
              {meter.percent !== null ? (
                <span
                  className={`rounded-full px-2 py-0.5 text-[0.62rem] font-semibold ${
                    meter.percent >= 95
                      ? "bg-clay-soft text-clay"
                      : meter.percent >= 80
                        ? "bg-amber-50 text-amber-800"
                        : "bg-forest/10 text-forest-deep"
                  }`}
                >
                  {meter.percent}%
                </span>
              ) : null}
            </div>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-charcoal">
              {meter.used.toLocaleString("en-IN")}
              <span className="ml-1.5 text-sm font-normal text-charcoal/45">
                / {meter.limit === null ? "∞" : meter.limit.toLocaleString("en-IN")}
              </span>
            </p>
            <div className="mt-3">
              <MeterBar percent={meter.percent} />
            </div>
            <p className="mt-2.5 text-[0.65rem] leading-4 text-charcoal/50">
              {usagePeriodLabel(meter.meter)}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:gap-4">
        {[
          { label: "Lifetime leads", value: usage.leads_total, icon: Activity },
          { label: "Lifetime bookings", value: usage.bookings_total, icon: CalendarDays },
          { label: "Messages sent", value: usage.messages_sent_total, icon: MessageSquareText },
          { label: "Active channels", value: usage.channels_active, icon: Users },
        ].map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs sm:p-5">
              <div className="flex items-center justify-between">
                <p className="text-[0.62rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                  {metric.label}
                </p>
                <Icon aria-hidden="true" className="size-3.5 text-charcoal/35" />
              </div>
              <p className="mt-2 text-xl font-semibold tracking-tight text-charcoal">
                {metric.value.toLocaleString("en-IN")}
              </p>
            </div>
          );
        })}
      </div>

      <Surface>
        <SectionHeader
          eyebrow="Daily activity"
          title={`Leads and messages · last ${days} days`}
          description="UTC-dated counts of new leads and outbound message deliveries."
          action={
            <div className="flex rounded-xl border border-charcoal/10 bg-charcoal/5 p-1">
              {DAY_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setDays(option)}
                  aria-pressed={days === option}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                    days === option
                      ? "bg-white text-charcoal shadow-xs"
                      : "text-charcoal/55 hover:text-charcoal"
                  }`}
                >
                  {option}d
                </button>
              ))}
            </div>
          }
        />
        <div className="p-5 sm:p-6">
          {usageQuery.isFetching ? (
            <div className="mb-3 flex items-center gap-2 text-[0.65rem] text-charcoal/50">
              <span className="size-2 animate-pulse rounded-full bg-forest" />
              Refreshing series…
            </div>
          ) : null}
          <TenantUsageChart series={usage.series} />
        </div>
      </Surface>
    </div>
  );
}
