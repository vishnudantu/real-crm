import { useState } from "react";
import { LoaderCircle, MapPin, Sun } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { updateProjectCoordinates } from "./solarApi";

const HYDERABAD = { latitude: 17.385, longitude: 78.4867 };

interface CoordinatesFormProps {
  projectId: string;
  projectName: string;
  isAdmin: boolean;
  onSaved: () => void | Promise<void>;
}

export function CoordinatesForm({ projectId, projectName, isAdmin, onSaved }: CoordinatesFormProps) {
  const [latitude, setLatitude] = useState(String(HYDERABAD.latitude));
  const [longitude, setLongitude] = useState(String(HYDERABAD.longitude));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Latitude must be a number between -90 and 90.");
      return;
    }
    if (!Number.isFinite(lng) || lng < -180 || lng > 180) {
      setError("Longitude must be a number between -180 and 180.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateProjectCoordinates(projectId, lat, lng);
      await onSaved();
    } catch (err: unknown) {
      setError(errorMessage(err, "Failed to save coordinates."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-2xl bg-[#141b16] p-6 text-ivory sm:p-8">
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <span className="grid size-12 place-items-center rounded-full bg-amber-300/15 text-amber-200">
          <Sun aria-hidden="true" className="size-6" />
        </span>
        <h3 className="mt-3 text-lg font-semibold tracking-tight">Set the site to see its sun</h3>
        <p className="mt-1.5 text-xs leading-relaxed text-ivory/60">
          <span className="font-medium text-ivory/80">{projectName}</span> has no latitude/longitude
          yet. Add the site coordinates to compute sunrise, sunset, and seasonal sun paths.
        </p>

        {!isAdmin ? (
          <p className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-xs text-ivory/60">
            Ask an administrator to set this project's coordinates to unlock the sun-path studio.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="mt-5 w-full space-y-3 text-left">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="site-latitude" className="text-[0.65rem] font-semibold tracking-wider text-ivory/55 uppercase">
                  Latitude
                </label>
                <input
                  id="site-latitude"
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  required
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-white/[0.05] px-3 py-2 text-sm text-ivory focus:border-amber-300/60 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="site-longitude" className="text-[0.65rem] font-semibold tracking-wider text-ivory/55 uppercase">
                  Longitude
                </label>
                <input
                  id="site-longitude"
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  required
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-white/[0.05] px-3 py-2 text-sm text-ivory focus:border-amber-300/60 focus:outline-none"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                setLatitude(String(HYDERABAD.latitude));
                setLongitude(String(HYDERABAD.longitude));
              }}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-200/80 hover:text-amber-200"
            >
              <MapPin aria-hidden="true" className="size-3" />
              Use Hyderabad default ({HYDERABAD.latitude}, {HYDERABAD.longitude})
            </button>

            {error && (
              <p role="alert" className="rounded-lg border border-rose-300/30 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={saving}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-amber-300 px-4 py-2.5 text-xs font-semibold text-[#141b16] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
              {saving ? "Saving coordinates…" : "Save & open sun studio"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
