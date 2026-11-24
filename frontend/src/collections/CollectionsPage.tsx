import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  HandCoins,
  RefreshCw,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { useInventoryProjects } from "../inventory/useInventoryProjects";
import {
  inventoryCardClasses,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
} from "../inventory/inventoryUi";
import { paiseToRupeesFormat } from "../inventory/inventoryModel";
import { createPromise, fetchCalendar, fetchEscalations, fetchStats } from "./collectionsApi";
import {
  currentMonth,
  monthLabel,
  orderedSeverityGroups,
  overdueRows,
  shiftMonth,
  sortEscalationRows,
} from "./collectionsModel";
import type { CalendarRow } from "./collectionsModel";

function StatTile({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "good" | "bad" }) {
  const toneClass =
    tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-rose-700" : "text-charcoal";
  return (
    <div className="rounded-xl border border-charcoal/10 bg-white p-4 shadow-xs">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-charcoal/55">{label}</div>
      <div className={`mt-1.5 text-xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function SeverityChip({ severity }: { severity: string }) {
  const upper = severity.toUpperCase();
  const cls =
    upper === "CRITICAL" || upper === "HIGH"
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : upper === "MEDIUM"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-charcoal/15 bg-charcoal/5 text-charcoal/65";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${cls}`}>
      {upper}
    </span>
  );
}

function PromiseForm({
  row,
  onSaved,
}: {
  row: CalendarRow;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const rupees = Number(amount);
    if (!Number.isFinite(rupees) || rupees < 0 || !date) {
      setError("Enter a valid amount (₹) and promise date.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createPromise(row.installment_id, {
        amount_paise: Math.round(rupees * 100),
        promised_on: date,
        note: note.trim() || null,
      });
      setOpen(false);
      setAmount("");
      setDate("");
      setNote("");
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "Failed to save the promise."));
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-[11px] font-semibold text-forest hover:underline"
      >
        + Promise
      </button>
    );
  }
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-forest/20 bg-forest/5 p-3">
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          min="0"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Amount ₹"
          className={inventoryInputClasses}
        />
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className={inventoryInputClasses}
        />
      </div>
      <input
        type="text"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note (optional)"
        className={inventoryInputClasses}
      />
      {error && <p className="text-[11px] text-rose-700">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={() => void submit()} disabled={saving} className={inventoryPrimaryButton}>
          {saving ? "Saving…" : "Save promise"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-[11px] font-semibold text-charcoal/60">
          Cancel
        </button>
      </div>
    </div>
  );
}

export function CollectionsPage() {
  const queryClient = useQueryClient();
  const { projects, isLoading: projectsLoading } = useInventoryProjects();
  const [projectId, setProjectId] = useState("");
  const [month, setMonth] = useState(currentMonth());

  const statsQuery = useQuery({
    queryKey: ["collections", "stats", projectId],
    queryFn: () => fetchStats(projectId || undefined),
  });
  const calendarQuery = useQuery({
    queryKey: ["collections", "calendar", projectId, month],
    queryFn: () => fetchCalendar(month, projectId || undefined),
  });
  const escalationsQuery = useQuery({
    queryKey: ["collections", "escalations", projectId],
    queryFn: () => fetchEscalations(projectId || undefined),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["collections"] });
  };

  const stats = statsQuery.data;
  const overdue = useMemo(() => overdueRows(calendarQuery.data?.days ?? []), [calendarQuery.data]);
  const groups = useMemo(
    () => orderedSeverityGroups(escalationsQuery.data?.groups ?? {}),
    [escalationsQuery.data],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-charcoal/50">
            <HandCoins aria-hidden="true" className="size-3.5" />
            Revenue
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Collections command centre
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Due calendar, escalation queue, promise capture, and recovery analytics for
            receivables. Finance teams live here daily.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div className="min-w-52">
            <label htmlFor="collections-project" className={inventoryLabelClasses}>Project</label>
            <select
              id="collections-project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={projectsLoading}
              className={inventoryInputClasses}
            >
              <option value="">All projects</option>
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

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Outstanding" value={stats ? paiseToRupeesFormat(stats.outstanding_paise) : "—"} tone="bad" />
        <StatTile label="Recovered (30d)" value={stats ? paiseToRupeesFormat(stats.recovered_30d_paise) : "—"} tone="good" />
        <StatTile label="Recovered (90d)" value={stats ? paiseToRupeesFormat(stats.recovered_90d_paise) : "—"} tone="good" />
        <StatTile
          label="Due this month"
          value={calendarQuery.data ? paiseToRupeesFormat(calendarQuery.data.due_this_month_paise) : "—"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Calendar */}
        <section className={`${inventoryCardClasses} p-4 sm:p-5 lg:col-span-2`}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
              <CalendarDays aria-hidden="true" className="size-4 text-charcoal/50" />
              Due calendar — {monthLabel(month)}
            </h2>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => setMonth(shiftMonth(month, -1))} className="rounded-lg border border-charcoal/15 p-1.5 text-charcoal/70 hover:bg-charcoal/5" aria-label="Previous month">
                <ChevronLeft aria-hidden="true" className="size-4" />
              </button>
              <button type="button" onClick={() => setMonth(shiftMonth(month, 1))} className="rounded-lg border border-charcoal/15 p-1.5 text-charcoal/70 hover:bg-charcoal/5" aria-label="Next month">
                <ChevronRight aria-hidden="true" className="size-4" />
              </button>
            </div>
          </div>
          {calendarQuery.isLoading ? (
            <p className="py-8 text-center text-xs text-charcoal/55">Loading calendar…</p>
          ) : calendarQuery.isError ? (
            <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
              {errorMessage(calendarQuery.error, "Failed to load the calendar.")}
            </p>
          ) : overdue.length === 0 ? (
            <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">
              No overdue installments for {monthLabel(month)}.
            </p>
          ) : (
            <ul className="space-y-2">
              {overdue.map((row) => (
                <li key={row.installment_id} className="rounded-lg border border-charcoal/10 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <span className="text-xs font-semibold text-charcoal">{row.unit_number}</span>
                      <span className="ml-2 text-[11px] text-charcoal/55">{row.customer_name ?? "—"}</span>
                      <div className="text-[11px] text-charcoal/55">
                        {row.milestone} · due {row.due_on} · {row.days_overdue}d overdue
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-semibold text-rose-700">
                        {paiseToRupeesFormat(row.outstanding_paise)}
                      </div>
                      <PromiseForm row={row} onSaved={refresh} />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Escalations */}
        <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-charcoal">
            <AlertTriangle aria-hidden="true" className="size-4 text-rose-500" />
            Escalation queue
          </h2>
          {escalationsQuery.isLoading ? (
            <p className="py-8 text-center text-xs text-charcoal/55">Loading escalations…</p>
          ) : escalationsQuery.isError ? (
            <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
              {errorMessage(escalationsQuery.error, "Failed to load escalations.")}
            </p>
          ) : groups.length === 0 ? (
            <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">
              No escalations. Receivables are healthy.
            </p>
          ) : (
            <div className="space-y-4">
              {groups.map((group) => (
                <div key={group.severity}>
                  <div className="mb-2 flex items-center gap-2">
                    <SeverityChip severity={group.severity} />
                    <span className="text-[11px] text-charcoal/50">{group.rows.length} bookings</span>
                  </div>
                  <ul className="space-y-2">
                    {sortEscalationRows(group.rows).slice(0, 5).map((row) => (
                      <li key={row.booking_id} className="rounded-lg border border-charcoal/10 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-charcoal">{row.unit_number}</span>
                          <span className="text-xs font-semibold text-rose-700">
                            {paiseToRupeesFormat(row.outstanding_paise)}
                          </span>
                        </div>
                        <div className="text-[11px] text-charcoal/55">
                          {row.days_overdue}d overdue · {row.overdue_installments} installments
                        </div>
                        <div className="mt-1 text-[11px] font-medium text-forest">{row.suggested_action}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <p className="flex items-center gap-2 text-[11px] text-charcoal/45">
        <CircleDollarSign aria-hidden="true" className="size-3.5" />
        Promises are recorded per installment and reflected in the calendar and recovery stats.
      </p>
    </div>
  );
}
