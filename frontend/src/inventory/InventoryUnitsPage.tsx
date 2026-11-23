import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileUp,
  Info,
  LayoutGrid,
  LoaderCircle,
  XCircle,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { projectTypeLabel } from "../admin/projectModel";
import { bulkCreateUnits, fetchUnits } from "./inventoryApi";
import type { BulkUnitCreateResponse, UnitStatus } from "./inventoryModel";
import { bulkCsvParse, statusLabel, UNIT_STATUSES, unitAuthoringGuidance } from "./inventoryModel";
import {
  inventoryCardClasses,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
  inventorySecondaryButton,
  StatusBadge,
} from "./inventoryUi";
import { useInventoryProjects } from "./useInventoryProjects";
import { UnitDetailDrawer } from "./UnitDetailDrawer";

const PAGE_SIZES = [10, 20, 50, 100] as const;
const CSV_PLACEHOLDER = `code,configuration,facing,carpet_area
A-101,2 BHK,East,1200
A-102,3 BHK,West,1450
A-103,3 BHK,North East,1500`;

export function InventoryUnitsPage() {
  const queryClient = useQueryClient();
  const { projects, isLoading: projectsLoading } = useInventoryProjects();
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState<UnitStatus | "ALL">("ALL");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState<BulkUnitCreateResponse | null>(null);
  const [importing, setImporting] = useState<"preview" | "commit" | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);

  useEffect(() => {
    setPage(1);
  }, [projectId, status, pageSize]);

  const unitsQuery = useQuery({
    queryKey: ["inventory", "units", projectId, "table", status, page, pageSize],
    queryFn: () => fetchUnits({ projectId, status, page, pageSize }),
    enabled: Boolean(projectId),
  });

  const units = unitsQuery.data?.items ?? [];
  const total = unitsQuery.data?.total ?? 0;
  const pages = unitsQuery.data?.pages ?? 0;

  const parsed = useMemo(() => bulkCsvParse(csvText, projectId), [csvText, projectId]);
  const selectedProject = projects.find((project) => project.id === projectId) ?? null;
  const authoring = unitAuthoringGuidance(selectedProject?.project_type);
  const typedProject = Boolean(selectedProject?.project_type);
  const resultByIndex = useMemo(
    () => new Map((preview?.results ?? []).map((result) => [result.index, result])),
    [preview],
  );
  const commitDisabled =
    importing !== null ||
    parsed.rows.length === 0 ||
    parsed.errors.length > 0 ||
    preview === null ||
    !preview.dry_run ||
    preview.failed > 0;

  const runImport = async (dryRun: boolean) => {
    if (!projectId) {
      setImportError("Select a project before importing units.");
      return;
    }
    if (parsed.rows.length === 0) {
      setImportError("Paste CSV with at least one valid row first.");
      return;
    }
    if (parsed.errors.length > 0) {
      setImportError("Fix the highlighted CSV rows before running the import.");
      return;
    }
    setImporting(dryRun ? "preview" : "commit");
    setImportError(null);
    try {
      const response = await bulkCreateUnits(parsed.rows, dryRun);
      setPreview(response);
      if (dryRun) {
        setNotice(
          response.failed === 0
            ? `Dry run passed: ${response.created} rows ready to import.`
            : `Dry run found ${response.failed} problem rows. Fix collisions before committing.`,
        );
      } else {
        await queryClient.invalidateQueries({ queryKey: ["inventory"] });
        if (response.failed === 0) {
          setNotice(`Import committed: ${response.created} units created.`);
          setCsvText("");
          setPreview(null);
        } else {
          setImportError(
            `Partial import: ${response.created} created, ${response.failed} failed. ` +
              "Rows already created are now duplicates — remove them from the CSV and run a fresh dry run before committing again.",
          );
          setNotice(null);
        }
      }
    } catch (err: unknown) {
      setImportError(errorMessage(err, "The bulk import request failed."));
    } finally {
      setImporting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <Link to="/admin/inventory" className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal/55 hover:text-charcoal">
            <ArrowLeft aria-hidden="true" className="size-3.5" />
            Back to inventory map
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Units & bulk import
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Page through every canonical unit, then paste CSV to validate and import new stock
            with a server-side dry run before anything is committed.
          </p>
        </div>
        <Link to="/admin/inventory" className={inventorySecondaryButton}>
          <LayoutGrid aria-hidden="true" className="size-3.5" />
          Inventory map
        </Link>
      </div>

      {notice && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          {notice}
        </p>
      )}

      <section aria-label="Units table" className={`${inventoryCardClasses} overflow-hidden`}>
        <div className="grid gap-4 border-b border-charcoal/10 p-4 md:grid-cols-3">
          <div>
            <label htmlFor="units-project" className={inventoryLabelClasses}>Project</label>
            <select
              id="units-project"
              value={projectId}
              onChange={(event) => {
                setProjectId(event.target.value);
                setPreview(null);
                setSelectedUnitId(null);
              }}
              disabled={projectsLoading || projects.length === 0}
              className={inventoryInputClasses}
            >
              {projects.length === 0 && <option value="">No projects available</option>}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="units-status" className={inventoryLabelClasses}>Status</label>
            <select
              id="units-status"
              value={status}
              onChange={(event) => setStatus(event.target.value as UnitStatus | "ALL")}
              className={inventoryInputClasses}
            >
              <option value="ALL">All statuses</option>
              {UNIT_STATUSES.map((unitStatus) => (
                <option key={unitStatus} value={unitStatus}>{statusLabel(unitStatus)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="units-page-size" className={inventoryLabelClasses}>Rows per page</label>
            <select
              id="units-page-size"
              value={pageSize}
              onChange={(event) => setPageSize(Number(event.target.value))}
              className={inventoryInputClasses}
            >
              {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-xs">
            <caption className="sr-only">Canonical inventory units for the selected project</caption>
            <thead className="border-b border-charcoal/10 bg-charcoal/[0.03] text-[0.65rem] font-semibold tracking-wider text-charcoal/55 uppercase">
              <tr>
                <th scope="col" className="px-4 py-3">Code</th>
                <th scope="col" className="px-4 py-3">Tower / floor</th>
                <th scope="col" className="px-4 py-3">Configuration</th>
                <th scope="col" className="px-4 py-3">Facing</th>
                <th scope="col" className="px-4 py-3">Carpet area</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-charcoal/8">
              {unitsQuery.isLoading && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-charcoal/55">
                    <span role="status" className="inline-flex items-center gap-2">
                      <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />
                      Loading units…
                    </span>
                  </td>
                </tr>
              )}
              {unitsQuery.isError && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-rose-700" role="alert">
                    {errorMessage(unitsQuery.error, "Failed to load units.")}
                    <button type="button" onClick={() => void unitsQuery.refetch()} className="ml-2 font-semibold underline">
                      Retry
                    </button>
                  </td>
                </tr>
              )}
              {!unitsQuery.isLoading && !unitsQuery.isError && units.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-charcoal/55">
                    No units found for this project{status !== "ALL" ? ` with status ${statusLabel(status)}` : ""}.
                  </td>
                </tr>
              )}
              {units.map((unit) => (
                <tr key={unit.id} className="hover:bg-charcoal/[0.025]">
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setSelectedUnitId(unit.id)}
                      aria-label={`Open ${unit.internal_code}, ${statusLabel(unit.status)}`}
                      className="font-mono text-xs font-bold text-charcoal underline-offset-2 hover:underline"
                    >
                      {unit.internal_code}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-charcoal/70">
                    {[unit.tower, unit.floor].filter(Boolean).join(" / ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-charcoal/70">{unit.configuration ?? "—"}</td>
                  <td className="px-4 py-3 text-charcoal/70">{unit.facing ?? "—"}</td>
                  <td className="px-4 py-3 text-charcoal/70">
                    {unit.carpet_area_sqft ? `${unit.carpet_area_sqft.toLocaleString("en-IN")} sqft` : "—"}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={unit.status} /></td>
                  <td className="px-4 py-3 whitespace-nowrap text-charcoal/55">
                    {new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(unit.updated_at))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col items-center justify-between gap-3 border-t border-charcoal/10 px-4 py-3 sm:flex-row">
          <p aria-live="polite" className="text-xs text-charcoal/55">
            {total === 0 ? "No units" : `Page ${page} of ${pages} · ${total} units`}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1 || unitsQuery.isFetching}
              aria-label="Previous page"
              className={inventorySecondaryButton}
            >
              <ChevronLeft aria-hidden="true" className="size-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((value) => Math.min(pages || value, value + 1))}
              disabled={page >= pages || unitsQuery.isFetching}
              aria-label="Next page"
              className={inventorySecondaryButton}
            >
              Next
              <ChevronRight aria-hidden="true" className="size-3.5" />
            </button>
          </div>
        </div>
      </section>

      {typedProject && (
        <p role="note" className="flex items-start gap-2 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs leading-relaxed text-sky-900">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-sky-600" />
          <span>
            <strong>{projectTypeLabel(selectedProject?.project_type)} project.</strong>{" "}
            {authoring.summary}
          </span>
        </p>
      )}

      <section aria-label="Bulk CSV import" className={`${inventoryCardClasses} p-5`}>
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-charcoal/5 text-charcoal">
            <FileUp aria-hidden="true" className="size-4" />
          </span>
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">Bulk import units</h2>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-charcoal/60">
              Paste CSV with a header row. Required: <code className="rounded bg-charcoal/5 px-1 font-mono">code</code>.
              Optional: <code className="rounded bg-charcoal/5 px-1 font-mono">configuration, facing, carpet_area, built_up_area, tower, floor, plot_number, position, status</code>.
              New units are created as AVAILABLE by default (DRAFT and APPROVED are also accepted).
              Validation runs as a server dry run first; nothing is written until you commit.
            </p>
            {typedProject && (
              <p className="mt-2 max-w-3xl rounded-lg border border-amber-200/70 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-900">
                {authoring.requiresTower || authoring.requiresFloor ? (
                  <>For this project each row must include <code className="rounded bg-white/70 px-1 font-mono">tower</code> and <code className="rounded bg-white/70 px-1 font-mono">floor</code>{authoring.disallowsPlotNumber ? <>; <code className="rounded bg-white/70 px-1 font-mono">plot_number</code> must stay empty</> : null}. </>
                ) : authoring.requiresPlotNumber ? (
                  <>For this project each row must include <code className="rounded bg-white/70 px-1 font-mono">plot_number</code>; <code className="rounded bg-white/70 px-1 font-mono">tower</code> must stay empty and <code className="rounded bg-white/70 px-1 font-mono">floor</code> may only hold a ground/basement block such as G or B1. </>
                ) : null}
                Rows that break these rules fail the dry run with a per-row explanation.
              </p>
            )}
          </div>
        </div>

        <div className="mt-4">
          <label htmlFor="bulk-csv" className={inventoryLabelClasses}>CSV rows</label>
          <textarea
            id="bulk-csv"
            value={csvText}
            onChange={(event) => {
              setCsvText(event.target.value);
              setPreview(null);
              setImportError(null);
            }}
            placeholder={CSV_PLACEHOLDER}
            rows={6}
            spellCheck={false}
            className={`${inventoryInputClasses} font-mono leading-relaxed`}
          />
        </div>

        {importError && (
          <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {importError}
          </p>
        )}

        {parsed.errors.length > 0 && (
          <div role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <p className="text-xs font-semibold text-rose-800">
              {parsed.errors.length} CSV {parsed.errors.length === 1 ? "error" : "errors"} — fix before importing
            </p>
            <ul className="mt-1.5 space-y-1 text-[11px] text-rose-700">
              {parsed.errors.map((error) => (
                <li key={`${error.row}-${error.message}`}>Line {error.row}: {error.message}</li>
              ))}
            </ul>
          </div>
        )}

        {parsed.rows.length > 0 && (
          <div className="mt-4 overflow-x-auto rounded-xl border border-charcoal/10">
            <table className="w-full min-w-[680px] text-left text-xs">
              <caption className="sr-only">Bulk import row preview with server validation results</caption>
              <thead className="border-b border-charcoal/10 bg-charcoal/[0.03] text-[0.65rem] font-semibold tracking-wider text-charcoal/55 uppercase">
                <tr>
                  <th scope="col" className="px-3 py-2.5">Row</th>
                  <th scope="col" className="px-3 py-2.5">Code</th>
                  <th scope="col" className="px-3 py-2.5">Configuration</th>
                  <th scope="col" className="px-3 py-2.5">Tower / floor</th>
                  <th scope="col" className="px-3 py-2.5">Plot</th>
                  <th scope="col" className="px-3 py-2.5">Carpet area</th>
                  <th scope="col" className="px-3 py-2.5">Validation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal/8">
                {parsed.rows.map((row, index) => {
                  const result = resultByIndex.get(index);
                  const failed = result?.ok === false;
                  return (
                    <tr key={`${row.internal_code}-${index}`} className={failed ? "bg-rose-50" : result?.ok ? "bg-emerald-50/40" : ""}>
                      <td className="px-3 py-2.5 text-charcoal/55">{index + 1}</td>
                      <td className="px-3 py-2.5 font-mono font-semibold">{row.internal_code}</td>
                      <td className="px-3 py-2.5 text-charcoal/70">{row.configuration ?? "—"}</td>
                      <td className="px-3 py-2.5 text-charcoal/70">{[row.tower, row.floor].filter(Boolean).join(" / ") || "—"}</td>
                      <td className="px-3 py-2.5 text-charcoal/70">{row.plot_number ?? "—"}</td>
                      <td className="px-3 py-2.5 text-charcoal/70">{row.carpet_area_sqft ?? "—"}</td>
                      <td className="px-3 py-2.5">
                        {failed ? (
                          <span className="inline-flex items-start gap-1.5 font-medium text-rose-700">
                            <XCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                            {result.reason ?? "Rejected by server"}
                          </span>
                        ) : result?.ok ? (
                          <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700">
                            <CheckCircle2 aria-hidden="true" className="size-3.5" />
                            {preview?.dry_run ? "Ready to import" : "Created"}
                          </span>
                        ) : (
                          <span className="text-charcoal/45">Awaiting dry run</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-charcoal/10 pt-4">
          <p className="text-[11px] text-charcoal/55">
            {parsed.rows.length > 0
              ? `${parsed.rows.length} valid rows parsed${preview ? ` · ${preview.failed} server errors` : ""}`
              : "Paste CSV above to preview rows."}
            {parsed.rows.length > 0 && !preview && " Run a dry run before committing."}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void runImport(true)}
              disabled={importing !== null || parsed.rows.length === 0 || parsed.errors.length > 0}
              className={inventorySecondaryButton}
            >
              {importing === "preview" && <LoaderCircle aria-hidden="true" className="size-3.5 motion-safe:animate-spin" />}
              {importing === "preview" ? "Validating…" : "Validate (dry run)"}
            </button>
            <button
              type="button"
              onClick={() => void runImport(false)}
              disabled={commitDisabled}
              title={
                !preview
                  ? "Run a successful dry run first"
                  : preview.failed > 0
                    ? "Resolve the failed rows and re-run the dry run before committing"
                    : undefined
              }
              className={inventoryPrimaryButton}
            >
              {importing === "commit" && <LoaderCircle aria-hidden="true" className="size-3.5 motion-safe:animate-spin" />}
              {importing === "commit" ? "Committing…" : "Commit import"}
            </button>
          </div>
        </div>
      </section>

      {selectedUnitId && (
        <UnitDetailDrawer
          unitId={selectedUnitId}
          projectType={selectedProject?.project_type}
          onClose={() => setSelectedUnitId(null)}
          onChanged={(message) => setNotice(message)}
        />
      )}
    </div>
  );
}
