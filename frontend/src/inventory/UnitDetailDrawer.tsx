import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BookCheck,
  Clock,
  History,
  Hourglass,
  LoaderCircle,
  LockOpen,
  Pencil,
  ShieldCheck,
  Sun,
  Timer,
  Trash2,
  X,
} from "lucide-react";
import { SunPathStudio } from "../solar/SunPathStudio";
import { useModalFocus } from "../shared/useModalFocus";
import { errorMessage } from "../shared/apiRequest";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { fetchUnit, reserveHold, transitionUnit } from "./inventoryApi";
import type { HoldResponse } from "./inventoryModel";
import {
  holdCountdown,
  isUuid,
  MAX_HOLD_EXTENSIONS,
  statusLabel,
} from "./inventoryModel";
import {
  inventoryDangerButton,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
  inventorySecondaryButton,
  formatDateTime,
  StatusBadge,
  StatusIcon,
} from "./inventoryUi";
import {
  ConvertHoldDialog,
  ExtendHoldDialog,
  HoldForBuyerDialog,
  ReleaseHoldDialog,
} from "./HoldActionDialogs";
import { DeleteUnitDialog, EditUnitDialog } from "./UnitEditDialogs";

interface UnitDetailDrawerProps {
  unitId: string;
  onClose: () => void;
  onChanged: (message: string) => void | Promise<void>;
}

type DialogKind = "hold" | "extend" | "release" | "convert" | "edit" | "delete" | null;

export function UnitDetailDrawer({ unitId, onClose, onChanged }: UnitDetailDrawerProps) {
  const { user } = useAdminUser();
  const queryClient = useQueryClient();
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [activeHold, setActiveHold] = useState<HoldResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reserving, setReserving] = useState(false);
  const [unblocking, setUnblocking] = useState(false);
  const [unblockReason, setUnblockReason] = useState("");
  const [approved, setApproved] = useState(false);
  const [showSunStudio, setShowSunStudio] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const {
    data: unit,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["inventory", "units", unitId, "detail"],
    queryFn: () => fetchUnit(unitId),
  });

  // The unit detail response carries no hold object; recover the active hold id
  // from the most recent hold-sourced status event's metadata.
  const historyHoldId = useMemo(() => {
    const events = unit?.status_history ?? [];
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const event = events[i];
      if (event.source !== "HOLD" && event.source !== "BOOKING") continue;
      const holdId = event.event_meta?.hold_id;
      if (isUuid(holdId)) return holdId;
    }
    return null;
  }, [unit]);

  useEffect(() => {
    setActiveHold(null);
    setDialog(null);
    setActionError(null);
    setApproved(false);
    setUnblockReason("");
  }, [unitId]);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const holdId = activeHold?.id ?? historyHoldId;
  const extensionCount = activeHold?.extension_count ?? null;
  const extensionLimitReached = extensionCount !== null && extensionCount >= MAX_HOLD_EXTENSIONS;
  const holdExpired =
    activeHold !== null &&
    activeHold.state === "ACTIVE" &&
    holdCountdown(activeHold.expires_at, nowMs) === "Expired";
  const canExtend =
    activeHold !== null && activeHold.state === "ACTIVE" && !extensionLimitReached && !holdExpired;
  const canConvert = activeHold !== null && activeHold.state === "ACTIVE" && !holdExpired;

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["inventory"] });
  };

  const handleHoldSuccess = async (hold: HoldResponse, message: string) => {
    setActiveHold(hold);
    setDialog(null);
    await invalidate();
    await refetch();
    await onChanged(message);
  };

  const handleReserve = async () => {
    if (!holdId) {
      setActionError("No active hold was found for this unit. Refresh the unit and try again.");
      return;
    }
    setReserving(true);
    setActionError(null);
    try {
      await reserveHold(holdId);
      await invalidate();
      await refetch();
      await onChanged(`Unit ${unit?.internal_code ?? ""} reserved.`);
    } catch (err: unknown) {
      setActionError(errorMessage(err, "Failed to reserve unit."));
    } finally {
      setReserving(false);
    }
  };

  const handleUnblock = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!unit) return;
    if (!approved) {
      setActionError("Confirm management approval before unblocking.");
      return;
    }
    if (!unblockReason.trim()) {
      setActionError("A reason is required to return this unit to available.");
      return;
    }
    setUnblocking(true);
    setActionError(null);
    try {
      await transitionUnit(unit.id, {
        to_status: "AVAILABLE",
        reason: unblockReason.trim(),
        source: "MANUAL",
        approved: true,
      });
      await invalidate();
      await refetch();
      await onChanged(`Unit ${unit.internal_code} unblocked and available.`);
    } catch (err: unknown) {
      setActionError(errorMessage(err, "Failed to unblock unit."));
    } finally {
      setUnblocking(false);
    }
  };

  const status = unit?.status;
  const isAdmin = user.role.name === "ADMIN";

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-end bg-charcoal/45 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={unit ? `Unit ${unit.internal_code} details` : "Unit details"}
        className="flex h-full w-full max-w-lg flex-col border-l border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[0.65rem] font-semibold tracking-[0.18em] text-charcoal/50 uppercase">
              Property inventory
            </p>
            <h2 className="mt-1 truncate text-xl font-semibold tracking-tight text-charcoal">
              {unit?.internal_code ?? "Unit details"}
            </h2>
            {unit && (
              <p className="mt-1 text-xs text-charcoal/60">
                {[unit.tower && `Tower ${unit.tower}`, unit.floor && `Floor ${unit.floor}`, unit.configuration]
                  .filter(Boolean)
                  .join(" · ") || "No tower/floor metadata"}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {status && <StatusBadge status={status} />}
            {isAdmin && unit && (
              <button
                type="button"
                onClick={() => setDialog("edit")}
                aria-label={`Edit unit ${unit.internal_code}`}
                title="Edit unit details"
                className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
              >
                <Pencil aria-hidden="true" className="size-4" />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close unit details"
              className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
          {isLoading && (
            <div role="status" className="flex items-center gap-2 text-sm text-charcoal/60">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              Loading unit details…
            </div>
          )}
          {isError && (
            <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
              {errorMessage(error, "Failed to load unit details.")}
              <button type="button" onClick={() => void refetch()} className="ml-2 font-semibold underline">
                Retry
              </button>
            </div>
          )}

          {unit && (
            <>
              {actionError && (
                <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
                  {actionError}
                </p>
              )}

              <section aria-label="Sun and facing" className="overflow-hidden rounded-xl border border-charcoal/10">
                <button
                  type="button"
                  onClick={() => setShowSunStudio((value) => !value)}
                  aria-expanded={showSunStudio}
                  className="flex w-full items-center justify-between gap-3 bg-white px-4 py-3 text-left transition-colors hover:bg-charcoal/[0.03]"
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                    <Sun aria-hidden="true" className="size-4 text-amber-500" />
                    Sun & facing
                  </span>
                  <span className="text-[11px] font-medium text-charcoal/50">
                    {showSunStudio ? "Hide" : "Explore"}
                  </span>
                </button>
                {showSunStudio && (
                  <SunPathStudio
                    projectId={unit.project_id}
                    projectName={`Unit ${unit.internal_code}`}
                    unitId={unit.id}
                    unitFacingText={unit.facing}
                    unitTower={unit.tower}
                    isAdmin={isAdmin}
                  />
                )}
              </section>

              <section aria-label="Unit identity" className="rounded-xl border border-charcoal/10 bg-white p-4">                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Configuration</dt>
                    <dd className="mt-0.5 font-medium">{unit.configuration ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Facing</dt>
                    <dd className="mt-0.5 font-medium">{unit.facing ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Carpet area</dt>
                    <dd className="mt-0.5 font-medium">
                      {unit.carpet_area_sqft ? `${unit.carpet_area_sqft.toLocaleString("en-IN")} sqft` : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Built-up area</dt>
                    <dd className="mt-0.5 font-medium">
                      {unit.built_up_area_sqft ? `${unit.built_up_area_sqft.toLocaleString("en-IN")} sqft` : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Position</dt>
                    <dd className="mt-0.5 font-medium">{unit.position ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Saleable</dt>
                    <dd className="mt-0.5 font-medium">{unit.saleable ? "Yes" : "No"}</dd>
                  </div>
                  {unit.views && (
                    <div className="col-span-2">
                      <dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Views</dt>
                      <dd className="mt-0.5 font-medium">{unit.views}</dd>
                    </div>
                  )}
                </dl>
                {unit.status_reason && (
                  <div className="mt-3 border-t border-charcoal/10 pt-3">
                    <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">Status reason</p>
                    <p className="mt-1 text-xs leading-relaxed text-charcoal/75">{unit.status_reason}</p>
                  </div>
                )}
              </section>

              {status === "AVAILABLE" && (
                <section aria-label="Hold actions" className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                    <Hourglass aria-hidden="true" className="size-4 text-emerald-600" />
                    Sell this unit
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-charcoal/60">
                    Place an exclusive hold for a buyer. The hold reserves the unit for a fixed
                    duration before it is released, reserved, or converted to a booking.
                  </p>
                  <button
                    type="button"
                    onClick={() => setDialog("hold")}
                    className={`${inventoryPrimaryButton} mt-3`}
                  >
                    <Timer aria-hidden="true" className="size-3.5" />
                    Hold for buyer
                  </button>
                </section>
              )}

              {(status === "ON_HOLD" || status === "RESERVED") && (
                <section aria-label="Active hold" className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                    <Hourglass aria-hidden="true" className="size-4 text-amber-600" />
                    Active hold
                  </h3>
                  {activeHold ? (
                    <div className="mt-3 space-y-2 text-xs">
                      <div className="flex items-center justify-between rounded-lg bg-white/80 px-3 py-2">
                        <span className="flex items-center gap-1.5 font-medium text-charcoal/70">
                          <Clock aria-hidden="true" className="size-3.5" />
                          {activeHold.state !== "ACTIVE"
                            ? `Hold ${activeHold.state.toLowerCase()}`
                            : holdExpired
                              ? "Hold expired"
                              : `Expires in ${holdCountdown(activeHold.expires_at, nowMs)}`}
                        </span>
                        <span className="font-mono text-[11px] text-charcoal/50">
                          {formatDateTime(activeHold.expires_at)}
                        </span>
                      </div>
                      <p className="text-charcoal/60">
                        Extensions used: {activeHold.extension_count} of {MAX_HOLD_EXTENSIONS}
                        {activeHold.lead_id ? ` · Lead ${activeHold.lead_id}` : " · No lead attached"}
                      </p>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs leading-relaxed text-charcoal/60">
                      {holdId
                        ? "Hold ID recovered from the status history. Placeholder countdown: the unit detail response does not include hold expiry or extension count, so a live countdown appears after an action on this hold."
                        : "No active hold could be identified from this unit's status history."}
                    </p>
                  )}
                  {holdExpired && (
                    <p className="mt-2 rounded-lg border border-amber-300 bg-white/80 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
                      This hold has expired. Release it to return the unit to Available, then place
                      a fresh hold. The backend expires holds lazily, so the status may still show
                      On hold until it is released or re-claimed.
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setDialog("extend")}
                      disabled={!canExtend}
                      title={
                        extensionLimitReached
                          ? "Maximum of 2 extensions reached"
                          : holdExpired
                            ? "This hold has expired and can no longer be extended"
                            : !activeHold
                              ? "Extend needs hold details (expiry and extension count), which the unit detail response does not include. They appear after you place or extend a hold in this session."
                              : undefined
                      }
                      className={inventorySecondaryButton}
                    >
                      <Timer aria-hidden="true" className="size-3.5" />
                      Extend{extensionCount !== null ? ` (${extensionCount}/${MAX_HOLD_EXTENSIONS})` : ""}
                    </button>
                    {status === "ON_HOLD" && (
                      <>
                        <button
                          type="button"
                          onClick={() => setDialog("release")}
                          disabled={!holdId}
                          title={!holdId ? "No active hold identified" : undefined}
                          className={inventoryDangerButton}
                        >
                          Release
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleReserve()}
                          disabled={!holdId || reserving}
                          title={!holdId ? "No active hold identified" : undefined}
                          className={inventorySecondaryButton}
                        >
                          {reserving ? (
                            <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
                          ) : (
                            <ShieldCheck aria-hidden="true" className="size-3.5" />
                          )}
                          {reserving ? "Reserving…" : "Reserve"}
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => setDialog("convert")}
                      disabled={!canConvert}
                      title={
                        !activeHold
                          ? "Convert needs hold details (state, lead, expiry), which the unit detail response does not include. They appear after you place a hold in this session."
                          : holdExpired
                            ? "This hold has expired and can no longer be converted"
                            : undefined
                      }
                      className={inventoryPrimaryButton}
                    >
                      <BookCheck aria-hidden="true" className="size-3.5" />
                      Convert to booking
                    </button>
                  </div>
                </section>
              )}

              {status === "BLOCKED" && isAdmin && (
                <section aria-label="Unblock unit" className="rounded-xl border border-rose-200 bg-rose-50/50 p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                    <LockOpen aria-hidden="true" className="size-4 text-rose-600" />
                    Unblock unit
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-charcoal/60">
                    Returns the unit to Available. This transition requires management approval.
                  </p>
                  <form noValidate onSubmit={handleUnblock} className="mt-3 space-y-3">
                    <div>
                      <label htmlFor="unblock-reason" className={inventoryLabelClasses}>
                        Reason <span className="text-rose-500">*</span>
                      </label>
                      <textarea
                        id="unblock-reason"
                        value={unblockReason}
                        onChange={(event) => setUnblockReason(event.target.value)}
                        rows={2}
                        maxLength={2000}
                        placeholder="e.g. Legal hold cleared by management"
                        className={inventoryInputClasses}
                      />
                    </div>
                    <label htmlFor="unblock-approved" className="flex items-start gap-2.5 text-xs text-charcoal/75">
                      <input
                        id="unblock-approved"
                        type="checkbox"
                        checked={approved}
                        onChange={(event) => setApproved(event.target.checked)}
                        className="mt-0.5 size-4 rounded border-charcoal/30 text-forest focus:ring-forest/30"
                      />
                      <span>I have management approval to unblock this unit.</span>
                    </label>
                    <button
                      type="submit"
                      disabled={!approved || unblocking}
                      title={!approved ? "Confirm management approval to continue" : undefined}
                      className={inventoryPrimaryButton}
                    >
                      {unblocking && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
                      {unblocking ? "Unblocking…" : "Unblock and make available"}
                    </button>
                  </form>
                </section>
              )}

              <section aria-label="Status history" className="rounded-xl border border-charcoal/10 bg-white p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                  <History aria-hidden="true" className="size-4 text-charcoal/50" />
                  Status history
                </h3>
                {unit.status_history.length === 0 ? (
                  <p className="mt-2 text-xs text-charcoal/50">No status transitions recorded yet.</p>
                ) : (
                  <ol className="mt-3 space-y-0">
                    {[...unit.status_history].reverse().map((event) => (
                      <li key={event.id} className="relative border-l border-charcoal/15 pb-4 pl-4 last:pb-0">
                        <span className="absolute -left-[5px] top-1 grid size-2.5 place-items-center rounded-full bg-white">
                          <StatusIcon status={event.to_status} className="size-3 text-charcoal/60" />
                        </span>
                        <div className="flex flex-wrap items-center gap-1.5 text-xs">
                          <span className="font-medium text-charcoal/60">{statusLabel(event.from_status)}</span>
                          <ArrowRight aria-hidden="true" className="size-3 text-charcoal/40" />
                          <span className="font-semibold">{statusLabel(event.to_status)}</span>
                          <span className="rounded bg-charcoal/5 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-charcoal/55 uppercase">
                            {event.source}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[11px] text-charcoal/50">{formatDateTime(event.effective_at)}</p>
                        {event.reason && (
                          <p className="mt-1 text-xs leading-relaxed text-charcoal/70">{event.reason}</p>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              {status === "DRAFT" && isAdmin && (
                <section aria-label="Delete draft unit" className="rounded-xl border border-rose-200 bg-rose-50/50 p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
                    <Trash2 aria-hidden="true" className="size-4 text-rose-600" />
                    Delete draft unit
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-charcoal/60">
                    Permanently removes this draft unit. The server only allows it when the unit
                    has no hold and no linked booking; otherwise cancel the unit instead.
                  </p>
                  <button
                    type="button"
                    onClick={() => setDialog("delete")}
                    className={`${inventoryDangerButton} mt-3`}
                  >
                    <Trash2 aria-hidden="true" className="size-3.5" />
                    Delete unit
                  </button>
                </section>
              )}
            </>
          )}
        </div>
      </div>

      {unit && dialog === "hold" && (
        <HoldForBuyerDialog unit={unit} onClose={() => setDialog(null)} onSuccess={handleHoldSuccess} />
      )}
      {unit && dialog === "extend" && activeHold && (
        <ExtendHoldDialog
          hold={activeHold}
          unitCode={unit.internal_code}
          onClose={() => setDialog(null)}
          onSuccess={handleHoldSuccess}
        />
      )}
      {unit && dialog === "release" && holdId && (
        <ReleaseHoldDialog
          holdId={holdId}
          unitCode={unit.internal_code}
          onClose={() => setDialog(null)}
          onSuccess={handleHoldSuccess}
        />
      )}
      {unit && dialog === "convert" && activeHold && (
        <ConvertHoldDialog
          hold={activeHold}
          unitCode={unit.internal_code}
          onClose={() => setDialog(null)}
          onSuccess={handleHoldSuccess}
        />
      )}
      {unit && dialog === "edit" && (
        <EditUnitDialog
          unit={unit}
          onClose={() => setDialog(null)}
          onSaved={async (_updated, message) => {
            setDialog(null);
            await invalidate();
            await refetch();
            await onChanged(message);
          }}
        />
      )}
      {unit && dialog === "delete" && (
        <DeleteUnitDialog
          unit={unit}
          onClose={() => setDialog(null)}
          onDeleted={async (message) => {
            setDialog(null);
            await invalidate();
            await onChanged(message);
            onClose();
          }}
        />
      )}
    </div>
  );
}
