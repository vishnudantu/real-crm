import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";
import { errorMessage } from "../shared/apiRequest";
import { createUnit } from "./inventoryApi";
import type { Unit, UnitCreateRequest } from "./inventoryModel";
import {
  inventoryInputClasses,
  inventoryLabelClasses,
  inventoryPrimaryButton,
  inventorySecondaryButton,
} from "./inventoryUi";

interface CreateUnitDialogProps {
  projectId: string;
  projectType?: string | null;
  onClose: () => void;
  onCreated: (code: string) => void | Promise<void>;
}

function nullable(value: string): string | null {
  return value.trim() || null;
}

function positiveInt(value: string): number | null {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

/** Manually create a single unit (starts as DRAFT). Type-aware hints shown. */
export function CreateUnitDialog({ projectId, projectType, onClose, onCreated }: CreateUnitDialogProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [code, setCode] = useState("");
  const [configuration, setConfiguration] = useState("");
  const [tower, setTower] = useState("");
  const [floor, setFloor] = useState("");
  const [position, setPosition] = useState("");
  const [carpetArea, setCarpetArea] = useState("");
  const [builtUpArea, setBuiltUpArea] = useState("");
  const [plotNumber, setPlotNumber] = useState("");
  const [facing, setFacing] = useState("");
  const [views, setViews] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: UnitCreateRequest) => createUnit(payload),
    onSuccess: (unit: Unit) => onCreated(unit.internal_code),
    onError: (err: unknown) => setFormError(errorMessage(err, "Failed to create unit.")),
  });

  const needsTower = projectType === "APARTMENT" || projectType === "COMMERCIAL";
  const needsPlot = projectType === "VILLA" || projectType === "PLOT";

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!code.trim()) {
      setFormError("A unit code is required (e.g. A-101).");
      return;
    }
    if (carpetArea.trim() && positiveInt(carpetArea) === null) {
      setFormError("Carpet area must be a positive whole number (sqft), or left blank.");
      return;
    }
    if (builtUpArea.trim() && positiveInt(builtUpArea) === null) {
      setFormError("Built-up area must be a positive whole number (sqft), or left blank.");
      return;
    }
    if (needsTower && (!tower.trim() || !floor.trim())) {
      setFormError("This project type requires a tower and a floor.");
      return;
    }
    if (needsPlot && !plotNumber.trim()) {
      setFormError("This project type requires a plot number.");
      return;
    }
    setFormError(null);
    mutation.mutate({
      project_id: projectId,
      internal_code: code.trim(),
      configuration: nullable(configuration),
      tower: nullable(tower),
      floor: nullable(floor),
      position: nullable(position),
      carpet_area_sqft: carpetArea.trim() ? positiveInt(carpetArea) : null,
      built_up_area_sqft: builtUpArea.trim() ? positiveInt(builtUpArea) : null,
      plot_number: nullable(plotNumber),
      facing: nullable(facing),
      views: nullable(views),
      saleable: true,
      status: "DRAFT",
      status_reason: null,
      rera_disclosure_json: {},
    });
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Add unit"
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold tracking-tight text-charcoal">Add a unit</h3>
            <p className="mt-1 text-[11px] leading-relaxed text-charcoal/55">
              New units start as DRAFT. Publish them from the unit detail once details are confirmed.
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close add unit" className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal">
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div className="p-5">
          <form noValidate onSubmit={submit} className="space-y-4">
            {formError && (
              <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
                {formError}
              </p>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="create-code" className={inventoryLabelClasses}>Unit code <span className="text-rose-500">*</span></label>
                <input id="create-code" value={code} maxLength={64} onChange={(e) => setCode(e.target.value)} placeholder="e.g. A-101" className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-configuration" className={inventoryLabelClasses}>Configuration</label>
                <input id="create-configuration" value={configuration} maxLength={100} onChange={(e) => setConfiguration(e.target.value)} placeholder="e.g. 3 BHK" className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-tower" className={inventoryLabelClasses}>Tower{needsTower && <span className="text-rose-500"> *</span>}</label>
                <input id="create-tower" value={tower} maxLength={64} onChange={(e) => setTower(e.target.value)} className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-floor" className={inventoryLabelClasses}>Floor{needsTower && <span className="text-rose-500"> *</span>}</label>
                <input id="create-floor" value={floor} maxLength={64} onChange={(e) => setFloor(e.target.value)} className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-position" className={inventoryLabelClasses}>Position</label>
                <input id="create-position" value={position} maxLength={64} onChange={(e) => setPosition(e.target.value)} placeholder="e.g. Corner" className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-plot" className={inventoryLabelClasses}>Plot number{needsPlot && <span className="text-rose-500"> *</span>}</label>
                <input id="create-plot" value={plotNumber} maxLength={64} onChange={(e) => setPlotNumber(e.target.value)} className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-carpet" className={inventoryLabelClasses}>Carpet area (sqft)</label>
                <input id="create-carpet" inputMode="numeric" value={carpetArea} onChange={(e) => setCarpetArea(e.target.value)} className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-builtup" className={inventoryLabelClasses}>Built-up area (sqft)</label>
                <input id="create-builtup" inputMode="numeric" value={builtUpArea} onChange={(e) => setBuiltUpArea(e.target.value)} className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-facing" className={inventoryLabelClasses}>Facing</label>
                <input id="create-facing" value={facing} maxLength={64} onChange={(e) => setFacing(e.target.value)} placeholder="e.g. East" className={inventoryInputClasses} />
              </div>
              <div>
                <label htmlFor="create-views" className={inventoryLabelClasses}>Views</label>
                <input id="create-views" value={views} maxLength={255} onChange={(e) => setViews(e.target.value)} placeholder="e.g. Lake, garden" className={inventoryInputClasses} />
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-charcoal/10 pt-4">
              <button type="button" onClick={onClose} disabled={mutation.isPending} className={inventorySecondaryButton}>Cancel</button>
              <button type="submit" disabled={mutation.isPending} className={inventoryPrimaryButton}>
                {mutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
                {mutation.isPending ? "Creating…" : "Create unit"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
