import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";
import { errorMessage } from "../shared/apiRequest";
import { deleteUnit, updateUnit } from "./inventoryApi";
import type { Unit, UnitUpdateRequest } from "./inventoryModel";
import {
  inventoryDangerButton,
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
  inventorySecondaryButton,
} from "./inventoryUi";

interface DialogShellProps {
  title: string;
  description: string;
  onClose: () => void;
  children: React.ReactNode;
}

function DialogShell({ title, description, onClose, children }: DialogShellProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold tracking-tight text-charcoal">{title}</h3>
            <p className="mt-1 text-[11px] leading-relaxed text-charcoal/55">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={`Close ${title}`}
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function nullable(value: string): string | null {
  return value.trim() || null;
}

function positiveInt(value: string): number | null {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

interface EditUnitDialogProps {
  unit: Unit;
  onClose: () => void;
  onSaved: (updated: Unit, message: string) => void | Promise<void>;
}

/** Edit the mutable identity/physical fields. Code and status are read-only. */
export function EditUnitDialog({ unit, onClose, onSaved }: EditUnitDialogProps) {
  const [configuration, setConfiguration] = useState(unit.configuration ?? "");
  const [tower, setTower] = useState(unit.tower ?? "");
  const [floor, setFloor] = useState(unit.floor ?? "");
  const [position, setPosition] = useState(unit.position ?? "");
  const [carpetArea, setCarpetArea] = useState(
    unit.carpet_area_sqft != null ? String(unit.carpet_area_sqft) : "",
  );
  const [builtUpArea, setBuiltUpArea] = useState(
    unit.built_up_area_sqft != null ? String(unit.built_up_area_sqft) : "",
  );
  const [plotNumber, setPlotNumber] = useState(unit.plot_number ?? "");
  const [facing, setFacing] = useState(unit.facing ?? "");
  const [views, setViews] = useState(unit.views ?? "");
  const [saleable, setSaleable] = useState(unit.saleable);
  const [reraJson, setReraJson] = useState(JSON.stringify(unit.rera_disclosure_json ?? {}, null, 2));
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: UnitUpdateRequest) => updateUnit(unit.id, payload),
    onSuccess: (updated) => onSaved(updated, `Unit ${unit.internal_code} updated.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to update unit.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (carpetArea.trim() && positiveInt(carpetArea) === null) {
      setFormError("Carpet area must be a positive whole number (sqft), or left blank.");
      return;
    }
    if (builtUpArea.trim() && positiveInt(builtUpArea) === null) {
      setFormError("Built-up area must be a positive whole number (sqft), or left blank.");
      return;
    }
    let rera: Record<string, unknown> = {};
    try {
      const parsed: unknown = JSON.parse(reraJson.trim() || "{}");
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setFormError("RERA disclosure must be a JSON object.");
        return;
      }
      rera = parsed as Record<string, unknown>;
    } catch {
      setFormError("RERA disclosure is not valid JSON.");
      return;
    }
    setFormError(null);
    mutation.mutate({
      configuration: nullable(configuration),
      tower: nullable(tower),
      floor: nullable(floor),
      position: nullable(position),
      carpet_area_sqft: carpetArea.trim() ? positiveInt(carpetArea) : null,
      built_up_area_sqft: builtUpArea.trim() ? positiveInt(builtUpArea) : null,
      plot_number: nullable(plotNumber),
      facing: nullable(facing),
      views: nullable(views),
      saleable,
      rera_disclosure_json: rera,
    });
  };

  return (
    <DialogShell
      title={`Edit unit ${unit.internal_code}`}
      description="The unit code and status are fixed. Status changes go through the hold and transition actions so they stay in the audit history."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="edit-configuration" className={inventoryLabelClasses}>Configuration</label>
            <input id="edit-configuration" value={configuration} maxLength={100}
              onChange={(e) => setConfiguration(e.target.value)} placeholder="e.g. 3 BHK"
              className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-facing" className={inventoryLabelClasses}>Facing</label>
            <input id="edit-facing" value={facing} maxLength={64}
              onChange={(e) => setFacing(e.target.value)} placeholder="e.g. East"
              className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-tower" className={inventoryLabelClasses}>Tower</label>
            <input id="edit-tower" value={tower} maxLength={64}
              onChange={(e) => setTower(e.target.value)} className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-floor" className={inventoryLabelClasses}>Floor</label>
            <input id="edit-floor" value={floor} maxLength={64}
              onChange={(e) => setFloor(e.target.value)} className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-position" className={inventoryLabelClasses}>Position</label>
            <input id="edit-position" value={position} maxLength={64}
              onChange={(e) => setPosition(e.target.value)} placeholder="e.g. Corner"
              className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-plot-number" className={inventoryLabelClasses}>Plot number</label>
            <input id="edit-plot-number" value={plotNumber} maxLength={64}
              onChange={(e) => setPlotNumber(e.target.value)} className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-carpet-area" className={inventoryLabelClasses}>Carpet area (sqft)</label>
            <input id="edit-carpet-area" inputMode="numeric" value={carpetArea}
              onChange={(e) => setCarpetArea(e.target.value)} className={inventoryInputClasses} />
          </div>
          <div>
            <label htmlFor="edit-built-up-area" className={inventoryLabelClasses}>Built-up area (sqft)</label>
            <input id="edit-built-up-area" inputMode="numeric" value={builtUpArea}
              onChange={(e) => setBuiltUpArea(e.target.value)} className={inventoryInputClasses} />
          </div>
        </div>
        <div>
          <label htmlFor="edit-views" className={inventoryLabelClasses}>Views</label>
          <input id="edit-views" value={views} maxLength={255}
            onChange={(e) => setViews(e.target.value)} placeholder="e.g. Lake, garden"
            className={inventoryInputClasses} />
        </div>
        <div>
          <label htmlFor="edit-rera" className={inventoryLabelClasses}>RERA disclosure (JSON object)</label>
          <textarea id="edit-rera" value={reraJson} rows={4} spellCheck={false}
            onChange={(e) => setReraJson(e.target.value)}
            className={`${inventoryInputClasses} font-mono text-[11px]`} />
        </div>
        <label htmlFor="edit-saleable" className="flex items-center gap-2.5 text-xs text-charcoal/75">
          <input id="edit-saleable" type="checkbox" checked={saleable}
            onChange={(e) => setSaleable(e.target.checked)}
            className="size-4 rounded border-charcoal/30 text-forest focus:ring-forest/30" />
          <span>Saleable (available for holds and bookings)</span>
        </label>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={inventoryPrimaryButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}

interface DeleteUnitDialogProps {
  unit: Unit;
  onClose: () => void;
  onDeleted: (message: string) => void | Promise<void>;
}

/** Confirms an irreversible delete. Only DRAFT units reach this dialog, and the
 * server re-checks status, holds, and linked bookings before removing anything. */
export function DeleteUnitDialog({ unit, onClose, onDeleted }: DeleteUnitDialogProps) {
  const [confirmation, setConfirmation] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => deleteUnit(unit.id),
    onSuccess: () => onDeleted(`Draft unit ${unit.internal_code} deleted.`),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to delete unit.")),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (confirmation.trim() !== unit.internal_code) {
      setFormError(`Type ${unit.internal_code} exactly to confirm deletion.`);
      return;
    }
    setFormError(null);
    mutation.mutate();
  };

  return (
    <DialogShell
      title={`Delete draft unit ${unit.internal_code}`}
      description="This permanently removes the unit. Only untouched draft units can be deleted; the server rejects the request if a hold or booking exists. Cancel a progressed unit instead of deleting it."
      onClose={onClose}
    >
      <form noValidate onSubmit={submit} className="space-y-4">
        {formError && (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
            {formError}
          </p>
        )}
        <div>
          <label htmlFor="delete-unit-confirmation" className={inventoryLabelClasses}>
            Type <span className="font-mono">{unit.internal_code}</span> to confirm
          </label>
          <input id="delete-unit-confirmation" value={confirmation} autoComplete="off"
            onChange={(e) => setConfirmation(e.target.value)} className={inventoryInputClasses} />
        </div>
        <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>
            Keep unit
          </button>
          <button type="submit" disabled={mutation.isPending} className={inventoryDangerButton}>
            {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
            {mutation.isPending ? "Deleting…" : "Delete draft unit"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
