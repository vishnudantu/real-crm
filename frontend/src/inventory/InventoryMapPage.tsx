import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Building2,
  LayoutGrid,
  List,
  LoaderCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { ApiError } from "../auth/api";
import { fetchAvailability, fetchUnits } from "./inventoryApi";
import type { UnitStatus } from "./inventoryModel";
import {
  groupUnitsByFloorTower,
  statusLabel,
  statusVisual,
  UNIT_STATUSES,
} from "./inventoryModel";
import {
  CELL_TONES,
  inventoryCardClasses,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventorySecondaryButton,
  LEGEND_DOT_TONES,
  ProjectBadge,
  StatusIcon,
} from "./inventoryUi";
import { useInventoryProjects } from "./useInventoryProjects";
import { UnitDetailDrawer } from "./UnitDetailDrawer";

const MAP_PAGE_SIZE = 1000;

/** Render a 422 envelope's field-level detail (e.g. "project_id: invalid UUID")
 * so the user sees *which* field failed, not just "Request validation failed". */
function describeLoadError(error: unknown): string {
  if (error instanceof ApiError && error.details.length > 0) {
    const fields = error.details
      .map((d) => [d.field, d.message].filter(Boolean).join(": "))
      .filter(Boolean)
      .join("; ");
    if (fields) return `${error.message} — ${fields}`;
  }
  return errorMessage(error, "Failed to load inventory.");
}

export function InventoryMapPage() {
  const { projects, isLoading: projectsLoading, isError: projectsError, error: projectsLoadError } =
    useInventoryProjects();
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState<UnitStatus | "ALL">("ALL");
  const [search, setSearch] = useState("");
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeTower, setActiveTower] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);

  const unitsQuery = useQuery({
    queryKey: ["inventory", "units", projectId, "map", status],
    queryFn: () => fetchUnits({ projectId, status, page: 1, pageSize: MAP_PAGE_SIZE }),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
  });

  const availabilityQuery = useQuery({
    queryKey: ["inventory", "availability", projectId],
    queryFn: () => fetchAvailability(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
  });

  const filteredUnits = useMemo(() => {
    const query = search.trim().toLowerCase();
    const items = unitsQuery.data?.items ?? [];
    if (!query) return items;
    return items.filter((unit) =>
      [unit.internal_code, unit.configuration, unit.facing, unit.tower, unit.floor]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(query)),
    );
  }, [search, unitsQuery.data]);

  const groups = useMemo(() => groupUnitsByFloorTower(filteredUnits), [filteredUnits]);
  const units = unitsQuery.data?.items ?? [];
  const counts = availabilityQuery.data?.counts ?? {};
  const selectedProject = projects.find((project) => project.id === projectId);

  // Active tower: default to the first, reset when the project changes, and
  // fall back to the first tower if the current selection no longer matches.
  const visibleTower = useMemo(() => {
    if (groups.length === 0) return null;
    return groups.find((tower) => tower.tower === activeTower) ?? groups[0];
  }, [groups, activeTower]);

  const refresh = async () => {
    await Promise.all([unitsQuery.refetch(), availabilityQuery.refetch()]);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2 text-[0.65rem] font-semibold tracking-[0.18em] text-charcoal/50 uppercase">
            <LayoutGrid aria-hidden="true" className="size-3.5" />
            Property inventory
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Live unit map
          </h1>
          {selectedProject && (
            <div className="mt-2">
              <ProjectBadge name={selectedProject.name} />
            </div>
          )}
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Scan availability by tower and floor, then open any unit to manage its hold,
            reservation, or booking lifecycle. Status refreshes every 30 seconds.
          </p>
        </div>
        <Link to="/admin/inventory/units" className={inventorySecondaryButton}>
          <List aria-hidden="true" className="size-3.5" />
          Units list & bulk import
        </Link>
      </div>

      {notice && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          {notice}
        </p>
      )}

      <section aria-label="Inventory filters" className={`${inventoryCardClasses} p-4`}>
        <div className="grid gap-4 md:grid-cols-[minmax(220px,1fr)_minmax(220px,1fr)_auto] md:items-end">
          <div>
            <label htmlFor="inventory-project" className={inventoryLabelClasses}>
              Project
            </label>
            <select
              id="inventory-project"
              value={projectId}
              onChange={(event) => {
                setProjectId(event.target.value);
                setSelectedUnitId(null);
                setNotice(null);
                setActiveTower(null);
              }}
              disabled={projectsLoading || projects.length === 0}
              className={inventoryInputClasses}
            >
              {projects.length === 0 && <option value="">No projects available</option>}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="inventory-search" className={inventoryLabelClasses}>
              Search code, configuration, or facing
            </label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 mt-0.5 size-3.5 -translate-y-1/2 text-charcoal/40" />
              <input
                id="inventory-search"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="e.g. A-101, 3 BHK, East"
                className={`${inventoryInputClasses} pl-9`}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={!projectId || unitsQuery.isFetching || availabilityQuery.isFetching}
            className={inventorySecondaryButton}
          >
            <RefreshCw aria-hidden="true" className={`size-3.5 ${unitsQuery.isFetching ? "motion-safe:animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        <fieldset className="mt-4 border-t border-charcoal/10 pt-4">
          <legend className="sr-only">Filter units by status</legend>
          <div className="flex flex-wrap gap-2" aria-label="Status filters">
            <button
              type="button"
              aria-pressed={status === "ALL"}
              onClick={() => setStatus("ALL")}
              className={`min-h-8 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                status === "ALL"
                  ? "border-charcoal bg-charcoal text-ivory"
                  : "border-charcoal/15 bg-white text-charcoal/65 hover:bg-charcoal/5"
              }`}
            >
              All statuses
            </button>
            {UNIT_STATUSES.map((unitStatus) => (
              <button
                key={unitStatus}
                type="button"
                aria-pressed={status === unitStatus}
                onClick={() => setStatus(unitStatus)}
                className={`inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  status === unitStatus
                    ? "border-charcoal bg-charcoal text-ivory"
                    : "border-charcoal/15 bg-white text-charcoal/65 hover:bg-charcoal/5"
                }`}
              >
                <StatusIcon status={unitStatus} className="size-3" />
                {statusLabel(unitStatus)}
              </button>
            ))}
          </div>
        </fieldset>
      </section>

      {projectsError && (
        <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
          {errorMessage(projectsLoadError, "Failed to load projects.")}
        </p>
      )}

      <section aria-label="Availability summary" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-10">
        {UNIT_STATUSES.map((unitStatus) => {
          const visual = statusVisual(unitStatus);
          return (
            <button
              key={unitStatus}
              type="button"
              onClick={() => setStatus(status === unitStatus ? "ALL" : unitStatus)}
              aria-pressed={status === unitStatus}
              aria-label={`Filter by ${statusLabel(unitStatus)}, ${counts[unitStatus] ?? 0} units`}
              className={`${inventoryCardClasses} p-3 text-left transition-colors hover:border-charcoal/25 ${
                status === unitStatus ? "ring-2 ring-charcoal/20" : ""
              }`}
            >
              <span className="flex items-center gap-1.5 text-[10px] font-semibold text-charcoal/60">
                <span aria-hidden="true" className={`size-2 rounded-full ${LEGEND_DOT_TONES[visual.tone]}`} />
                <StatusIcon status={unitStatus} className="size-3" />
                {statusLabel(unitStatus)}
              </span>
              <span className="mt-2 block text-2xl font-semibold tracking-tight text-charcoal">
                {availabilityQuery.isLoading ? "…" : (counts[unitStatus] ?? 0)}
              </span>
            </button>
          );
        })}
      </section>

      <section aria-label="Unit status legend" className={`${inventoryCardClasses} flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3`}>
        <span className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Legend</span>
        {UNIT_STATUSES.map((unitStatus) => {
          const visual = statusVisual(unitStatus);
          return (
            <span key={unitStatus} className="inline-flex items-center gap-1.5 text-[11px] font-medium text-charcoal/65">
              <span aria-hidden="true" className={`size-2 rounded-full ${LEGEND_DOT_TONES[visual.tone]}`} />
              <StatusIcon status={unitStatus} className="size-3" />
              {statusLabel(unitStatus)}
            </span>
          );
        })}
      </section>

      <section aria-label="Inventory unit map" className={`${inventoryCardClasses} min-h-64 p-4 sm:p-5`}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
            <Building2 aria-hidden="true" className="size-4 text-charcoal/50" />
            Tower & floor availability
          </h2>
          <p aria-live="polite" className="text-xs text-charcoal/55">
            {unitsQuery.isLoading
              ? "Loading units…"
              : `${filteredUnits.length} of ${unitsQuery.data?.total ?? units.length} units shown`}
          </p>
        </div>

        {(unitsQuery.isError || availabilityQuery.isError) && (
          <div role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
            {describeLoadError(unitsQuery.error ?? availabilityQuery.error)}
            <button type="button" onClick={() => void refresh()} className="ml-2 font-semibold underline">
              Retry
            </button>
          </div>
        )}

        {unitsQuery.isLoading && (
          <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-sm text-charcoal/60">
            <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />
            Loading unit map…
          </div>
        )}

        {!unitsQuery.isLoading && projectId && units.length === 0 && !unitsQuery.isError && (
          <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-center">
            <Building2 aria-hidden="true" className="size-8 text-charcoal/25" />
            <p className="text-sm font-semibold text-charcoal">No units match this view</p>
            <p className="max-w-md text-xs leading-relaxed text-charcoal/55">
              {status === "ALL"
                ? "This project has no inventory yet. Add units with the CSV bulk import."
                : `No units have status ${statusLabel(status)}. Choose another status filter.`}
            </p>
            <Link to="/admin/inventory/units" className={`${inventorySecondaryButton} mt-2`}>
              Open bulk import
            </Link>
          </div>
        )}

        {!unitsQuery.isLoading && units.length > 0 && filteredUnits.length === 0 && (
          <p className="py-12 text-center text-sm text-charcoal/55">
            No units match “{search}”. Clear the search to see all loaded units.
          </p>
        )}

        {!unitsQuery.isLoading && groups.length > 0 && (
          <>
            {/* Tower selector: keeps a 10-tower, 1000-unit project navigable
                without one giant canvas — one tower at a time, cleanly. */}
            {groups.length > 1 && (
              <div role="tablist" aria-label="Towers" className="mb-4 flex flex-wrap gap-2">
                {groups.map((tower) => {
                  const active = visibleTower?.tower === tower.tower;
                  const towerUnitCount = tower.floors.reduce((sum, floor) => sum + floor.units.length, 0);
                  return (
                    <button
                      key={tower.tower}
                      role="tab"
                      type="button"
                      aria-selected={active}
                      onClick={() => setActiveTower(tower.tower)}
                      className={`inline-flex min-h-9 items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-colors ${
                        active
                          ? "border-forest bg-forest text-ivory shadow-xs"
                          : "border-charcoal/15 bg-white text-charcoal/70 hover:bg-charcoal/5"
                      }`}
                    >
                      <Building2 aria-hidden="true" className="size-3.5" />
                      {tower.tower === "Unassigned tower" ? tower.tower : `Tower ${tower.tower}`}
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                          active ? "bg-ivory/25 text-ivory" : "bg-charcoal/10 text-charcoal/60"
                        }`}
                      >
                        {towerUnitCount}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {visibleTower && (
              <section aria-label={`Tower ${visibleTower.tower} map`} className="rounded-xl border border-charcoal/10 bg-[#FAFAF7] p-3 sm:p-4">
                <h3 className="mb-3 text-xs font-semibold tracking-wider text-charcoal/65 uppercase">
                  {visibleTower.tower === "Unassigned tower"
                    ? visibleTower.tower
                    : `Tower ${visibleTower.tower}`}{" "}
                  · {visibleTower.floors.reduce((sum, floor) => sum + floor.units.length, 0)} units
                </h3>
                <div className="space-y-4">
                  {visibleTower.floors.map((floor) => (
                    <div key={floor.floor}>
                      <div className="mb-1.5 flex items-baseline gap-2">
                        <h4 className="text-[11px] font-semibold text-charcoal/55">
                          {floor.floor === "Unassigned floor" ? floor.floor : `Floor ${floor.floor}`}
                        </h4>
                        <span className="text-[10px] text-charcoal/40">{floor.units.length}</span>
                      </div>
                      <div
                        role="group"
                        aria-label={`${visibleTower.tower}, ${floor.floor}, ${floor.units.length} units`}
                        className="grid gap-1.5"
                        style={{
                          gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))",
                        }}
                      >
                        {floor.units.map((unit) => {
                          const visual = statusVisual(unit.status);
                          return (
                            <button
                              key={unit.id}
                              type="button"
                              onClick={() => setSelectedUnitId(unit.id)}
                              aria-label={`${unit.internal_code}, ${statusLabel(unit.status)}${unit.configuration ? `, ${unit.configuration}` : ""}`}
                              title={`${unit.internal_code} · ${unit.configuration ?? ""} · ${statusLabel(unit.status)}`}
                              className={`flex h-12 flex-col items-start justify-between rounded-md border px-1.5 py-1 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-1 ${CELL_TONES[visual.tone]}`}
                            >
                              <span className="flex w-full items-center justify-between gap-1">
                                <span className="truncate text-[10.5px] font-bold">{unit.internal_code}</span>
                                <StatusIcon status={unit.status} className="size-3 shrink-0" />
                              </span>
                              <span className="block w-full truncate text-[9px] font-semibold opacity-80">
                                {unit.configuration ?? statusLabel(unit.status)}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {(unitsQuery.data?.total ?? 0) > units.length && (
          <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
            This map loads the first {MAP_PAGE_SIZE} units for the selected project{status !== "ALL" ? " and status" : ""}.
            Use the paginated units list to inspect the remaining {Math.max(0, (unitsQuery.data?.total ?? 0) - units.length)} units.
          </p>
        )}
      </section>

      {selectedUnitId && (
        <UnitDetailDrawer
          unitId={selectedUnitId}
          projectType={projects.find((project) => project.id === projectId)?.project_type}
          onClose={() => setSelectedUnitId(null)}
          onChanged={(message) => setNotice(message)}
        />
      )}
    </div>
  );
}
