import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, LoaderCircle, RotateCcw, Save, Shield } from "lucide-react";
import { bulkUpdateTenantFeatures, fetchTenantFeatures, resetTenantFeatureOverride } from "./api";
import { errorMessage } from "../shared/apiRequest";
import {
  FEATURE_SOURCE_CATALOG_DEFAULT,
  FEATURE_SOURCE_OVERRIDE,
  FEATURE_SOURCE_PLAN,
  featureMatrixDiff,
  featureMatrixPayload,
} from "./operatorModel";
import type { TenantFeatureEntry } from "./operatorModel";
import { ErrorBlock, InlineNotice, LoadingBlock, primaryButtonClasses } from "./ui";

interface TenantEntitlementsTabProps {
  tenantId: string;
  canWrite: boolean;
}

function sourceLabel(source: string): string {
  if (source === FEATURE_SOURCE_OVERRIDE) return "Tenant override";
  if (source === FEATURE_SOURCE_PLAN) return "Plan";
  if (source === FEATURE_SOURCE_CATALOG_DEFAULT) return "Catalog default";
  return source;
}

function sourceTone(source: string): string {
  if (source === FEATURE_SOURCE_OVERRIDE)
    return "border-amber-400/40 bg-amber-50 text-amber-800";
  if (source === FEATURE_SOURCE_PLAN)
    return "border-forest/25 bg-forest/10 text-forest-deep";
  return "border-charcoal/15 bg-charcoal/5 text-charcoal/55";
}

export function TenantEntitlementsTab({ tenantId, canWrite }: TenantEntitlementsTabProps) {
  const queryClient = useQueryClient();
  const [staged, setStaged] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);

  const matrixQuery = useQuery({
    queryKey: ["operator", "tenants", tenantId, "features"],
    queryFn: () => fetchTenantFeatures(tenantId),
    enabled: Boolean(tenantId),
  });

  useEffect(() => {
    if (matrixQuery.data) setStaged({});
  }, [matrixQuery.data]);

  const rows = matrixQuery.data ?? [];
  const changes = useMemo(() => featureMatrixDiff(rows, staged), [rows, staged]);
  const effectiveFor = (row: TenantFeatureEntry) =>
    typeof staged[row.feature] === "boolean" ? (staged[row.feature] as boolean) : row.enabled;

  const saveMutation = useMutation({
    mutationFn: (features: Record<string, boolean>) => bulkUpdateTenantFeatures(tenantId, features),
    onSuccess: async () => {
      setStaged({});
      setNotice({ tone: "success", text: `${changes.length} entitlement change${changes.length === 1 ? "" : "s"} saved and audited.` });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "features"] });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "config"] });
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: errorMessage(error, "Failed to save entitlements.") });
    },
  });

  const resetMutation = useMutation({
    mutationFn: (feature: string) => resetTenantFeatureOverride(tenantId, feature),
    onMutate: (feature) => setResetting(feature),
    onSettled: () => setResetting(null),
    onSuccess: async (_, feature) => {
      setNotice({ tone: "success", text: `${feature} now follows the plan or catalog default.` });
      setStaged((previous) => {
        const next = { ...previous };
        delete next[feature];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "features"] });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "config"] });
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: errorMessage(error, "Failed to reset the override.") });
    },
  });

  if (matrixQuery.isLoading) {
    return <LoadingBlock label="Loading feature matrix…" />;
  }
  if (matrixQuery.isError) {
    return (
      <ErrorBlock
        message={
          matrixQuery.error instanceof Error
            ? matrixQuery.error.message
            : "Failed to load the entitlement matrix."
        }
        onRetry={() => void matrixQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-5">
      {notice ? <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice> : null}

      <div className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs">
        <div className="border-b border-charcoal/10 px-5 py-4 sm:px-6">
          <h3 className="text-sm font-semibold text-charcoal">
            {rows.filter((row) => effectiveFor(row)).length} of {rows.length} features enabled
          </h3>
          <p className="mt-1 text-xs text-charcoal/55">
            Resolution order: tenant override → plan bundle → catalog default.
            Saving writes overrides via PUT /operator/tenants/{'{id}'}/features.
          </p>
        </div>

        {rows.length === 0 ? (
          <p className="px-5 py-8 text-xs text-charcoal/55 sm:px-6">
            The feature catalog is empty. Seed the backend catalog to make
            entitlements controllable.
          </p>
        ) : (
          <ul className="divide-y divide-charcoal/5">
            {rows.map((row) => {
              const effective = effectiveFor(row);
              const stagedFlag = typeof staged[row.feature] === "boolean";
              return (
                <li key={row.feature} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-xs font-semibold text-charcoal">{row.label}</p>
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[0.58rem] font-semibold tracking-wider uppercase ${sourceTone(row.source)}`}
                      >
                        {sourceLabel(row.source)}
                      </span>
                      {stagedFlag ? (
                        <span className="inline-flex rounded-full border border-amber-400/40 bg-amber-50 px-2 py-0.5 text-[0.58rem] font-semibold tracking-wider text-amber-800 uppercase">
                          Staged
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-[0.68rem] leading-5 text-charcoal/55">{row.description}</p>
                    <p className="mt-1 font-mono text-[0.6rem] text-charcoal/40">{row.feature}</p>
                    {row.reason ? (
                      <p className="mt-1 text-[0.62rem] text-charcoal/50">
                        Last override reason: {row.reason}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    {canWrite && row.source === FEATURE_SOURCE_OVERRIDE ? (
                      <button
                        type="button"
                        disabled={resetting === row.feature}
                        onClick={() => {
                          setNotice(null);
                          resetMutation.mutate(row.feature);
                        }}
                        title="Remove the tenant override and fall back to plan/catalog"
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-charcoal/15 bg-white px-2.5 text-[0.65rem] font-semibold text-charcoal/65 transition-colors hover:bg-charcoal/5 disabled:opacity-50"
                      >
                        {resetting === row.feature ? (
                          <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
                        ) : (
                          <RotateCcw aria-hidden="true" className="size-3" />
                        )}
                        Reset
                      </button>
                    ) : null}
                    <button
                      type="button"
                      role="switch"
                      aria-checked={effective}
                      aria-label={`${row.label} enabled`}
                      disabled={!canWrite}
                      onClick={() => {
                        setNotice(null);
                        setStaged((previous) => ({
                          ...previous,
                          [row.feature]: !effective,
                        }));
                      }}
                      className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                        effective ? "border-forest/30 bg-forest" : "border-charcoal/20 bg-charcoal/10"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className={`absolute top-1/2 size-4 -translate-y-1/2 rounded-full bg-white shadow-sm transition-all ${
                          effective ? "left-[1.35rem]" : "left-0.5"
                        }`}
                      />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {canWrite ? (
        <div className="flex flex-col gap-3 rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
          <div className="flex items-center gap-2">
            <Shield aria-hidden="true" className="size-4 text-charcoal/50" />
            <h3 className="text-sm font-semibold text-charcoal">Staged changes</h3>
            <span className="rounded-full bg-charcoal/5 px-2 py-0.5 text-[0.62rem] font-semibold text-charcoal/70">
              {changes.length}
            </span>
          </div>
          {changes.length === 0 ? (
            <p className="text-xs text-charcoal/55">
              Toggle a feature above to stage a change; nothing is sent until you save.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {changes.map((change) => (
                <li key={change.feature} className="flex items-center gap-2 text-xs text-charcoal/70">
                  {change.to ? (
                    <ArrowUpRight aria-hidden="true" className="size-3.5 text-forest" />
                  ) : (
                    <ArrowDownRight aria-hidden="true" className="size-3.5 text-clay" />
                  )}
                  <span className="font-semibold text-charcoal">{change.label}</span>
                  <span>
                    {change.from ? "Enabled" : "Disabled"} →{" "}
                    <strong>{change.to ? "Enabled" : "Disabled"}</strong>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              disabled={changes.length === 0 || saveMutation.isPending}
              onClick={() => {
                setNotice(null);
                setStaged({});
              }}
              className="inline-flex min-h-10 items-center rounded-xl border border-charcoal/15 bg-white px-4 text-xs font-semibold text-charcoal/70 disabled:opacity-50"
            >
              Revert staged
            </button>
            <button
              type="button"
              disabled={changes.length === 0 || saveMutation.isPending}
              onClick={() => {
                setNotice(null);
                saveMutation.mutate(featureMatrixPayload(changes));
              }}
              className={primaryButtonClasses}
            >
              {saveMutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Save aria-hidden="true" className="size-4" />
              )}
              Save {changes.length > 0 ? `(${changes.length})` : ""}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-charcoal/55">
          You have read-only access to this tenant's entitlement matrix.
        </p>
      )}
    </div>
  );
}
