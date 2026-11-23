import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Compass,
  Clock,
  LayoutGrid,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useInventoryProjects } from "../inventory/useInventoryProjects";
import { inventoryInputClasses, inventoryLabelClasses } from "../inventory/inventoryUi";
import { paiseToRupeesFormat } from "../inventory/inventoryModel";
import {
  fetchConflicts,
  fetchHoldExpiry,
  fetchRecommendations,
  fetchRevenueMap,
  fetchUnsoldRisk,
} from "./intelligenceApi";
import {
  conflictLabel,
  hoursRemainingLabel,
  realizationPercent,
  sortByUrgency,
  sortUnsoldByRisk,
  statusTiles,
  towerAging,
} from "./intelligenceModel";
import { EmptyState, ErrorState, LoadingState, RiskChip, SectionCard } from "./intelligenceUi";

function unitDrawerLink(unitId: string): string {
  return `/admin/inventory?unit=${unitId}`;
}

export function InventoryIntelligencePage() {
  const { projects, isLoading: projectsLoading } = useInventoryProjects();
  const [projectId, setProjectId] = useState("");
  const [unitQuery, setUnitQuery] = useState("");

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);

  const enabled = Boolean(projectId);
  const baseKey = ["inventory-intelligence", projectId];

  const revenueQuery = useQuery({
    queryKey: [...baseKey, "revenue-map"],
    queryFn: () => fetchRevenueMap(projectId),
    enabled,
  });
  const holdsQuery = useQuery({
    queryKey: [...baseKey, "hold-expiry"],
    queryFn: () => fetchHoldExpiry(projectId),
    enabled,
  });
  const unsoldQuery = useQuery({
    queryKey: [...baseKey, "unsold-risk"],
    queryFn: () => fetchUnsoldRisk(projectId),
    enabled,
  });
  const conflictsQuery = useQuery({
    queryKey: [...baseKey, "conflicts"],
    queryFn: () => fetchConflicts(projectId),
    enabled,
  });
  const recommendationsQuery = useQuery({
    queryKey: [...baseKey, "recommendations", unitQuery],
    queryFn: () => fetchRecommendations(unitQuery.trim()),
    enabled: enabled && unitQuery.trim().length > 0,
  });

  const refresh = () => {
    void Promise.all([
      revenueQuery.refetch(),
      holdsQuery.refetch(),
      unsoldQuery.refetch(),
      conflictsQuery.refetch(),
    ]);
  };

  const revenue = revenueQuery.data;
  const tiles = useMemo(() => statusTiles(revenue?.by_status ?? {}), [revenue]);
  const aging = useMemo(() => towerAging(revenue?.rows ?? []), [revenue]);
  const urgentHolds = useMemo(
    () => sortByUrgency(holdsQuery.data?.items ?? []),
    [holdsQuery.data],
  );
  const unsold = useMemo(
    () => sortUnsoldByRisk(unsoldQuery.data?.items ?? []),
    [unsoldQuery.data],
  );
  const conflicts = conflictsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-charcoal/50">
            <Activity aria-hidden="true" className="size-3.5" />
            Property intelligence
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Inventory intelligence
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Revenue realization, hold-expiry risk, unsold-inventory aging, data-integrity
            conflicts, and alternative-unit recommendations for the selected project.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div className="min-w-56">
            <label htmlFor="ii-project" className={inventoryLabelClasses}>Project</label>
            <select
              id="ii-project"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={projectsLoading || projects.length === 0}
              className={inventoryInputClasses}
            >
              {projects.length === 0 && <option value="">No projects available</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={!enabled}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3 py-2 text-[11px] font-semibold text-charcoal/75 hover:bg-charcoal/5 disabled:opacity-50"
          >
            <RefreshCw aria-hidden="true" className="size-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {!enabled && (
        <div className="flex min-h-64 flex-col items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-8 text-center">
          <Compass aria-hidden="true" className="size-8 text-charcoal/25" />
          <p className="text-sm font-semibold text-charcoal">Select a project to begin</p>
        </div>
      )}

      {enabled && (
        <>
          {/* Revenue map */}
          <SectionCard
            title="Revenue map"
            subtitle="Value, realization and inventory aging by status and tower."
            icon={<BarChart3 aria-hidden="true" className="size-4 text-charcoal/50" />}
            actions={
              revenue && (
                <div className="text-right">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-charcoal/50">
                    Realization
                  </div>
                  <div className="text-xl font-semibold text-forest">
                    {realizationPercent(revenue.by_status, revenue.total_units)}%
                  </div>
                </div>
              )
            }
          >
            {revenueQuery.isLoading ? (
              <LoadingState label="Computing revenue map…" />
            ) : revenueQuery.isError ? (
              <ErrorState
                message={errorMessage(revenueQuery.error, "Failed to load revenue map.")}
                onRetry={refresh}
              />
            ) : !revenue || revenue.total_units === 0 ? (
              <EmptyState label="No inventory in this project yet." />
            ) : (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {tiles.map((tile) => (
                    <div
                      key={tile.status}
                      className="rounded-xl border border-charcoal/10 bg-charcoal/[0.02] p-3"
                    >
                      <div className="text-[10px] font-semibold uppercase tracking-wide text-charcoal/55">
                        {tile.label}
                      </div>
                      <div className="mt-1 text-2xl font-semibold text-charcoal">{tile.count}</div>
                    </div>
                  ))}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-xs">
                    <thead>
                      <tr className="border-b border-charcoal/10 text-[10px] uppercase tracking-wide text-charcoal/50">
                        <th className="py-2 pr-3 font-semibold">Tower</th>
                        <th className="py-2 pr-3 font-semibold">Units</th>
                        <th className="py-2 pr-3 font-semibold">Booked value</th>
                        <th className="py-2 font-semibold">Oldest (days)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {aging.map((row) => (
                        <tr key={row.tower} className="border-b border-charcoal/5">
                          <td className="py-2 pr-3 font-semibold text-charcoal">{row.tower}</td>
                          <td className="py-2 pr-3 text-charcoal/70">{row.units}</td>
                          <td className="py-2 pr-3 text-charcoal/70">
                            {paiseToRupeesFormat(row.bookedValuePaise)}
                          </td>
                          <td className="py-2 text-charcoal/70">{row.oldestAgeDays}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </SectionCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Hold expiry */}
            <SectionCard
              title="Hold-expiry risk"
              subtitle="Active holds most likely to lapse without converting."
              icon={<Clock aria-hidden="true" className="size-4 text-charcoal/50" />}
            >
              {holdsQuery.isLoading ? (
                <LoadingState label="Assessing holds…" />
              ) : holdsQuery.isError ? (
                <ErrorState
                  message={errorMessage(holdsQuery.error, "Failed to load hold-expiry risk.")}
                  onRetry={refresh}
                />
              ) : urgentHolds.length === 0 ? (
                <EmptyState label="No active holds at risk right now." />
              ) : (
                <ul className="space-y-2">
                  {urgentHolds.slice(0, 8).map((hold) => (
                    <li
                      key={hold.hold_id}
                      className="flex items-center justify-between gap-3 rounded-lg border border-charcoal/10 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <Link
                          to={unitDrawerLink(hold.unit_id)}
                          className="text-xs font-semibold text-forest hover:underline"
                        >
                          Unit {hold.unit_id.slice(0, 8)}…
                        </Link>
                        <div className="text-[11px] text-charcoal/55">
                          {hoursRemainingLabel(hold.hours_remaining)} · {hold.extension_count} ext used
                        </div>
                      </div>
                      <RiskChip risk={hold.risk} />
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            {/* Unsold risk */}
            <SectionCard
              title="Unsold-inventory risk"
              subtitle="Available units at risk of a prolonged selling period."
              icon={<AlertTriangle aria-hidden="true" className="size-4 text-charcoal/50" />}
            >
              {unsoldQuery.isLoading ? (
                <LoadingState label="Scoring unsold risk…" />
              ) : unsoldQuery.isError ? (
                <ErrorState
                  message={errorMessage(unsoldQuery.error, "Failed to load unsold risk.")}
                  onRetry={refresh}
                />
              ) : unsold.length === 0 ? (
                <EmptyState label="No available units at risk." />
              ) : (
                <ul className="space-y-2">
                  {unsold.slice(0, 8).map((unit) => (
                    <li
                      key={unit.unit_id}
                      className="flex items-center justify-between gap-3 rounded-lg border border-charcoal/10 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <Link
                          to={unitDrawerLink(unit.unit_id)}
                          className="text-xs font-semibold text-forest hover:underline"
                        >
                          {unit.internal_code}
                        </Link>
                        <div className="text-[11px] text-charcoal/55">
                          {unit.days_available} days on market
                        </div>
                      </div>
                      <RiskChip risk={unit.risk} />
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>

          {/* Conflicts */}
          {conflictsQuery.isError ? (
            <ErrorState
              message={errorMessage(conflictsQuery.error, "Failed to run conflict detection.")}
              onRetry={refresh}
            />
          ) : conflicts.length > 0 ? (
            <SectionCard
              title={`Data-integrity conflicts (${conflicts.length})`}
              subtitle="Inconsistent booking, reservation, payment or sale states — resolve before reporting."
              icon={<AlertTriangle aria-hidden="true" className="size-4 text-rose-500" />}
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {conflicts.map((conflict) => (
                  <div
                    key={`${conflict.unit_id}-${conflict.kind}`}
                    className="rounded-xl border border-rose-200 bg-rose-50 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-rose-600" />
                      <span className="text-xs font-semibold text-rose-800">
                        {conflictLabel(conflict.kind)}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[11px] leading-relaxed text-rose-700">
                      {conflict.detail}
                    </p>
                    <Link
                      to={unitDrawerLink(conflict.unit_id)}
                      className="mt-2 inline-block text-[11px] font-semibold text-rose-700 underline"
                    >
                      Resolve in unit drawer
                    </Link>
                  </div>
                ))}
              </div>
            </SectionCard>
          ) : (
            <SectionCard
              title="Data-integrity conflicts"
              subtitle="Inconsistent booking, reservation, payment or sale states."
              icon={<AlertTriangle aria-hidden="true" className="size-4 text-charcoal/50" />}
            >
              {conflictsQuery.isLoading ? (
                <LoadingState label="Checking for conflicts…" />
              ) : (
                <EmptyState label="No data-integrity conflicts detected. Inventory is consistent." />
              )}
            </SectionCard>
          )}

          {/* Recommendations */}
          <SectionCard
            title="Alternative-unit recommendations"
            subtitle="Enter a unit id to rank available alternatives by similarity."
            icon={<Sparkles aria-hidden="true" className="size-4 text-charcoal/50" />}
          >
            <div className="mb-4 max-w-md">
              <label htmlFor="ii-unit" className={inventoryLabelClasses}>Unit id</label>
              <input
                id="ii-unit"
                type="text"
                value={unitQuery}
                onChange={(event) => setUnitQuery(event.target.value)}
                placeholder="Paste a unit UUID to find similar available units"
                className={inventoryInputClasses}
              />
            </div>
            {!unitQuery.trim() ? (
              <EmptyState label="Enter a unit id above to see ranked alternatives." />
            ) : recommendationsQuery.isLoading ? (
              <LoadingState label="Ranking alternatives…" />
            ) : recommendationsQuery.isError ? (
              <ErrorState
                message={errorMessage(recommendationsQuery.error, "Failed to load recommendations.")}
              />
            ) : (recommendationsQuery.data?.items.length ?? 0) === 0 ? (
              <EmptyState label="No available alternatives matched that unit." />
            ) : (
              <ul className="space-y-2">
                {recommendationsQuery.data?.items.map((rec) => (
                  <li
                    key={rec.unit_id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-charcoal/10 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <Link
                        to={unitDrawerLink(rec.unit_id)}
                        className="text-xs font-semibold text-forest hover:underline"
                      >
                        {rec.internal_code}
                      </Link>
                      <div className="text-[11px] text-charcoal/55">{rec.reasons.join(" · ")}</div>
                    </div>
                    <span className="inline-flex items-center gap-1 rounded-full border border-forest/25 bg-forest/5 px-2 py-0.5 text-[10px] font-semibold text-forest">
                      {rec.score}% match
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <p className="flex items-center gap-2 text-[11px] text-charcoal/45">
            <LayoutGrid aria-hidden="true" className="size-3.5" />
            Recommendations rank available units only; sold and held units are never suggested.
          </p>
        </>
      )}
    </div>
  );
}
