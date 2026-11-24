import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Compass,
  FileText,
  MapPin,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useInventoryProjects } from "../inventory/useInventoryProjects";
import {
  inventoryCardClasses,
  inventoryInputClasses,
  inventoryLabelClasses,
} from "../inventory/inventoryUi";
import { paiseToRupeesFormat } from "../inventory/inventoryModel";
import { fetchAmenities, fetchConnectivity, fetchDemand, fetchReports, generateFacts } from "./cityIntelApi";
import {
  bestConfidence,
  categoryLabel,
  connectivityBand,
  distanceLabel,
  orderedCategories,
  sortDemand,
  sortReports,
} from "./cityIntelModel";

function ConfidenceChip({ confidence }: { confidence: string }) {
  const cls =
    confidence === "verified"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : confidence === "estimated"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cls}`}>
      {confidence}
    </span>
  );
}

export function CityIntelligencePage() {
  const queryClient = useQueryClient();
  const { projects, isLoading: projectsLoading } = useInventoryProjects();
  const [projectId, setProjectId] = useState("");
  const [factNotice, setFactNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);

  const enabled = Boolean(projectId);
  const demandQuery = useQuery({ queryKey: ["city-intel", "demand"], queryFn: fetchDemand });
  const amenitiesQuery = useQuery({
    queryKey: ["city-intel", "amenities", projectId],
    queryFn: () => fetchAmenities(projectId),
    enabled,
  });
  const connectivityQuery = useQuery({
    queryKey: ["city-intel", "connectivity", projectId],
    queryFn: () => fetchConnectivity(projectId),
    enabled,
  });
  const reportsQuery = useQuery({
    queryKey: ["city-intel", "reports", projectId],
    queryFn: () => fetchReports(projectId),
    enabled,
  });

  const demand = useMemo(() => sortDemand(demandQuery.data?.items ?? []), [demandQuery.data]);
  const categories = useMemo(
    () => orderedCategories(connectivityQuery.data?.by_category ?? []),
    [connectivityQuery.data],
  );
  const reports = useMemo(() => sortReports(reportsQuery.data?.items ?? []), [reportsQuery.data]);
  const amenities = amenitiesQuery.data?.items ?? [];

  const refresh = () => {
    setFactNotice(null);
    void queryClient.invalidateQueries({ queryKey: ["city-intel"] });
  };

  const onGenerateFacts = async () => {
    setFactNotice(null);
    try {
      const result = await generateFacts(projectId);
      setFactNotice(`${result.generated} DRAFT facts staged for review (not auto-approved).`);
    } catch (err) {
      setFactNotice(errorMessage(err, "Failed to generate facts."));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-charcoal/50">
            <Compass aria-hidden="true" className="size-3.5" />
            Property intelligence
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            City intelligence
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Catchment demand, curated location amenities, and source-verified locality reports.
            Curated data only — no geocoding, no invented risk scores.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div className="min-w-56">
            <label htmlFor="ci-project" className={inventoryLabelClasses}>Project</label>
            <select
              id="ci-project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
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
            className="inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3 py-2 text-[11px] font-semibold text-charcoal/75 hover:bg-charcoal/5"
          >
            <RefreshCw aria-hidden="true" className="size-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Demand */}
      <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-charcoal">
          <TrendingUp aria-hidden="true" className="size-4 text-charcoal/50" />
          Catchment demand by locality
        </h2>
        {demandQuery.isLoading ? (
          <p className="py-6 text-center text-xs text-charcoal/55">Aggregating demand…</p>
        ) : demandQuery.isError ? (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
            {errorMessage(demandQuery.error, "Failed to load demand.")}
          </p>
        ) : demand.length === 0 ? (
          <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">No projects yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-charcoal/10 text-[10px] uppercase tracking-wide text-charcoal/50">
                  <th className="py-2 pr-3 font-semibold">Locality</th>
                  <th className="py-2 pr-3 font-semibold">Leads</th>
                  <th className="py-2 pr-3 font-semibold">Bookings</th>
                  <th className="py-2 pr-3 font-semibold">Conversion</th>
                  <th className="py-2 pr-3 font-semibold">Median budget</th>
                  <th className="py-2 pr-3 font-semibold">Top band</th>
                  <th className="py-2 font-semibold">Top type</th>
                </tr>
              </thead>
              <tbody>
                {demand.map((row) => (
                  <tr key={row.project_id} className="border-b border-charcoal/5">
                    <td className="py-2 pr-3">
                      <div className="font-semibold text-charcoal">{row.project_name}</div>
                      <div className="text-[11px] text-charcoal/50">{row.locality}</div>
                    </td>
                    <td className="py-2 pr-3 text-charcoal/70">{row.lead_count}</td>
                    <td className="py-2 pr-3 text-charcoal/70">{row.booking_count}</td>
                    <td className="py-2 pr-3 text-charcoal/70">{row.conversion_pct}%</td>
                    <td className="py-2 pr-3 text-charcoal/70">
                      {row.median_budget_paise != null ? paiseToRupeesFormat(row.median_budget_paise) : "—"}
                    </td>
                    <td className="py-2 pr-3 text-charcoal/70">{row.top_price_band}</td>
                    <td className="py-2 text-charcoal/70">{row.top_property_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {enabled && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Connectivity */}
          <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                <MapPin aria-hidden="true" className="size-4 text-charcoal/50" />
                Connectivity
              </h2>
              {connectivityQuery.data && (
                <div className="text-right">
                  <div className="text-xl font-semibold text-forest">{connectivityQuery.data.score}/100</div>
                  <div className="text-[10px] uppercase tracking-wide text-charcoal/50">
                    {connectivityBand(connectivityQuery.data.score)}
                  </div>
                </div>
              )}
            </div>
            {connectivityQuery.isLoading ? (
              <p className="py-6 text-center text-xs text-charcoal/55">Scoring connectivity…</p>
            ) : connectivityQuery.isError ? (
              <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
                {errorMessage(connectivityQuery.error, "Failed to score connectivity.")}
              </p>
            ) : (
              <>
                <ul className="space-y-1.5">
                  {categories.map((c) => (
                    <li key={c.category} className="flex items-center justify-between text-xs">
                      <span className="text-charcoal/70">{categoryLabel(c.category)}</span>
                      <span className="text-charcoal/55">
                        {c.count > 0
                          ? `${c.count} · nearest ${c.nearest_km != null ? distanceLabel(c.nearest_km) : "—"}`
                          : "no data"}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] leading-relaxed text-charcoal/45">
                  Score is advisory, computed from curated POIs only. Distances are admin-supplied,
                  not geocoded.
                </p>
              </>
            )}
          </section>

          {/* Amenities list */}
          <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-charcoal">
              <Building2 aria-hidden="true" className="size-4 text-charcoal/50" />
              Curated amenities ({amenities.length})
            </h2>
            {amenitiesQuery.isLoading ? (
              <p className="py-6 text-center text-xs text-charcoal/55">Loading amenities…</p>
            ) : amenities.length === 0 ? (
              <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">
                No curated points of interest yet for this project.
              </p>
            ) : (
              <ul className="space-y-2">
                {amenities.slice(0, 8).map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 rounded-lg border border-charcoal/10 px-3 py-2">
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-charcoal">{a.name}</div>
                      <div className="text-[11px] text-charcoal/55">
                        {categoryLabel(a.category)} · {distanceLabel(a.distance_km)} · {a.travel_minutes} min
                      </div>
                    </div>
                    <ConfidenceChip confidence={a.confidence} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {/* Locality reports */}
      {enabled && (
        <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
              <FileText aria-hidden="true" className="size-4 text-charcoal/50" />
              Source-verified locality reports
            </h2>
            <button
              type="button"
              onClick={() => void onGenerateFacts()}
              className="rounded-lg border border-forest/25 bg-forest/5 px-3 py-1.5 text-[11px] font-semibold text-forest hover:bg-forest/10"
            >
              Generate DRAFT facts
            </button>
          </div>
          {factNotice && (
            <p className="mb-3 rounded-lg border border-forest/20 bg-forest/5 px-3 py-2 text-[11px] text-forest">
              {factNotice}
            </p>
          )}
          {reportsQuery.isLoading ? (
            <p className="py-6 text-center text-xs text-charcoal/55">Loading reports…</p>
          ) : reportsQuery.isError ? (
            <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
              {errorMessage(reportsQuery.error, "Failed to load reports.")}
            </p>
          ) : reports.length === 0 ? (
            <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">
              No locality reports authored yet for this project.
            </p>
          ) : (
            <ul className="space-y-3">
              {reports.map((report) => (
                <li key={report.id} className="rounded-xl border border-charcoal/10 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-charcoal">{report.title}</span>
                    <ConfidenceChip confidence={bestConfidence(report.sources)} />
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-charcoal/65">{report.body}</p>
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-charcoal/45">
                    {report.as_of && <span>as of {report.as_of}</span>}
                    <span>{report.sources.length} source(s)</span>
                    <span className="rounded bg-charcoal/5 px-1.5 py-0.5 font-semibold">{report.status}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
