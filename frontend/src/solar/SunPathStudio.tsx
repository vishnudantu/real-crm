import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, LoaderCircle, Pause, Play, RotateCcw, Save, Sun } from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { ApiError } from "../auth/api";
import {
  fetchSunPath,
  fetchUnitSunScore,
  upsertTowerOrientation,
} from "./solarApi";
import {
  COMPASS_FULL_NAMES,
  classifyExposure,
  dayForSeason,
  facadeSunLabel,
  facingTextToBearing,
  formatMinutesAsTime,
  isFacadeInSun,
  isoToLocal,
  localToMinutes,
  minutesToLocalTime,
  normalizeBearing,
  scoreUnitFacing,
  solarPosition,
  SEASONS,
} from "./solarModel";
import type { SeasonKey } from "./solarModel";
import { SunArcScene } from "./SunArcScene";
import { FacingDial } from "./FacingDial";
import { SunScoreBadge } from "./SunScoreBadge";
import { CoordinatesForm } from "./CoordinatesForm";

interface SunPathStudioProps {
  projectId: string;
  projectName: string;
  /** Optional unit context: when present, shows the unit sun-score badge and
   *  initialises the dial from the unit's facing. */
  unitId?: string;
  unitFacingText?: string | null;
  unitTower?: string | null;
  isAdmin?: boolean;
}

const DEFAULT_UTC_OFFSET = 5.5; // IST — the product is India-first.
const PLAY_SPEED_MINUTES_PER_SECOND = 40;

export function SunPathStudio({
  projectId,
  projectName,
  unitId,
  unitFacingText,
  unitTower,
  isAdmin = false,
}: SunPathStudioProps) {
  const queryClient = useQueryClient();
  const utcOffset = DEFAULT_UTC_OFFSET;

  const [season, setSeason] = useState<SeasonKey>("equinox");
  const [showAllSeasons, setShowAllSeasons] = useState(true);
  const [timeMinutes, setTimeMinutes] = useState(720);
  const [playing, setPlaying] = useState(false);
  const [bearing, setBearing] = useState(() => facingTextToBearing(unitFacingText) ?? 90);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(query.matches);
    const listener = (event: MediaQueryListEvent) => setReducedMotion(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  const sunPathQuery = useQuery({
    queryKey: ["solar", "sun-path", projectId],
    queryFn: () => fetchSunPath(projectId),
    retry: (failureCount, error) => {
      // Missing coordinates returns a 4xx — don't retry, show the empty state.
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
      return failureCount < 2;
    },
  });

  const sunPath = sunPathQuery.data;
  const coordinatesMissing =
    sunPathQuery.isError &&
    sunPathQuery.error instanceof ApiError &&
    (sunPathQuery.error.status === 400 || sunPathQuery.error.status === 422 ||
      /coordinates/i.test(sunPathQuery.error.message));

  const unitScoreQuery = useQuery({
    queryKey: ["solar", "sun-score", unitId],
    queryFn: () => fetchUnitSunScore(unitId as string),
    enabled: Boolean(unitId) && Boolean(sunPath),
    retry: false,
  });

  // Initialise bearing from the server-confirmed unit score when it arrives.
  useEffect(() => {
    if (unitScoreQuery.data) {
      setBearing(normalizeBearing(unitScoreQuery.data.facing_bearing));
    }
  }, [unitScoreQuery.data]);

  const activeDay = useMemo(
    () => (sunPath ? dayForSeason(sunPath.solstices_and_equinox, season) : null),
    [sunPath, season],
  );

  // Snap the scrubber into the new season's daylight window when data/season changes.
  useEffect(() => {
    if (!activeDay) return;
    const noon = localToMinutes(isoToLocal(activeDay.solar_noon, utcOffset));
    setTimeMinutes(noon);
  }, [activeDay, utcOffset]);

  const currentLocal = useMemo(() => {
    if (!activeDay) return null;
    const base = isoToLocal(activeDay.solar_noon, utcOffset);
    return minutesToLocalTime(timeMinutes, base);
  }, [activeDay, timeMinutes, utcOffset]);

  const position = useMemo(() => {
    if (!sunPath || !currentLocal) return { elevation: -1, azimuth: 180 };
    return solarPosition(sunPath.latitude, sunPath.longitude, currentLocal);
  }, [sunPath, currentLocal]);

  const inSun = isFacadeInSun(bearing, position.azimuth, position.elevation);
  const localScore = useMemo(() => scoreUnitFacing(bearing), [bearing]);
  const exposure = classifyExposure(bearing);

  // Play/pause animation loop.
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);
  useEffect(() => {
    if (!playing || !activeDay) return;
    const sunrise = localToMinutes(isoToLocal(activeDay.sunrise, utcOffset));
    const sunset = localToMinutes(isoToLocal(activeDay.sunset, utcOffset));
    const tick = (now: number) => {
      const last = lastTickRef.current ?? now;
      const deltaSeconds = (now - last) / 1000;
      lastTickRef.current = now;
      setTimeMinutes((value) => {
        const next = value + deltaSeconds * PLAY_SPEED_MINUTES_PER_SECOND;
        if (next >= sunset) {
          setPlaying(false);
          return sunset;
        }
        return Math.max(sunrise, next);
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTickRef.current = null;
    };
  }, [playing, activeDay, utcOffset]);

  const scrubRange = useMemo(() => {
    if (!activeDay) return { min: 0, max: 1440 };
    return {
      min: Math.floor(localToMinutes(isoToLocal(activeDay.sunrise, utcOffset))),
      max: Math.ceil(localToMinutes(isoToLocal(activeDay.sunset, utcOffset))),
    };
  }, [activeDay, utcOffset]);

  const orientationMutation = useMutation({
    mutationFn: (orientationDeg: number) =>
      upsertTowerOrientation(projectId, unitTower?.trim() || "Main", orientationDeg),
    onSuccess: async (data) => {
      setSaveNotice(`Tower "${data.tower_label}" bearing saved at ${Math.round(data.orientation_deg)}°.`);
      setSaveError(null);
      await queryClient.invalidateQueries({ queryKey: ["solar", "sun-score"] });
    },
    onError: (error: unknown) => {
      setSaveError(errorMessage(error, "Failed to save tower orientation."));
      setSaveNotice(null);
    },
  });

  const handleSaveOrientation = () => {
    orientationMutation.mutate(Math.round(bearing));
  };

  const handleCoordinatesSaved = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["solar", "sun-path", projectId] });
  }, [projectId, queryClient]);

  // ---------------------------------------------------------------------------
  // States
  // ---------------------------------------------------------------------------

  if (sunPathQuery.isLoading) {
    return (
      <div role="status" className="flex min-h-64 items-center justify-center gap-2 rounded-2xl bg-[#141b16] text-sm text-ivory/60">
        <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
        Loading sun path…
      </div>
    );
  }

  if (coordinatesMissing || (!sunPath && sunPathQuery.isError)) {
    // Only show the coordinate form when coordinates are actually missing;
    // other errors fall through to the generic error state below.
    if (coordinatesMissing) {
      return (
        <CoordinatesForm
          projectId={projectId}
          projectName={projectName}
          isAdmin={isAdmin}
          onSaved={handleCoordinatesSaved}
        />
      );
    }
  }

  if (sunPathQuery.isError || !sunPath) {
    return (
      <div role="alert" className="rounded-2xl border border-rose-300/30 bg-rose-950/40 p-5 text-sm text-rose-200">
        {errorMessage(sunPathQuery.error, "Failed to load the sun path for this project.")}
        <button
          type="button"
          onClick={() => void sunPathQuery.refetch()}
          className="ml-2 font-semibold underline"
        >
          Retry
        </button>
      </div>
    );
  }

  const towerLabel = unitTower?.trim() || "Main";
  const dialLabel = COMPASS_FULL_NAMES[localScore.facing_label];

  return (
    <div className="space-y-4 rounded-2xl bg-[#141b16] p-4 text-ivory sm:p-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-[0.65rem] font-semibold tracking-[0.18em] text-ivory/45 uppercase">
            <Sun aria-hidden="true" className="size-3.5" />
            Sun & facing studio
          </p>
          <h3 className="mt-1 text-lg font-semibold tracking-tight">{projectName}</h3>
          <p className="mt-0.5 text-[11px] text-ivory/45">
            {sunPath.latitude.toFixed(4)}°, {sunPath.longitude.toFixed(4)}° · times shown in IST
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-pressed={showAllSeasons}
            onClick={() => setShowAllSeasons((value) => !value)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors ${
              showAllSeasons
                ? "border-ivory/40 bg-ivory/10 text-ivory"
                : "border-ivory/15 text-ivory/60 hover:bg-ivory/5"
            }`}
          >
            <Layers aria-hidden="true" className="size-3.5" />
            All seasons
          </button>
        </div>
      </div>

      {/* Season toggle */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Season">
        {SEASONS.map((meta) => {
          const day = dayForSeason(sunPath.solstices_and_equinox, meta.key);
          return (
            <button
              key={meta.key}
              type="button"
              aria-pressed={season === meta.key}
              disabled={!day}
              onClick={() => setSeason(meta.key)}
              title={day ? `${meta.label} · ${day.day_length_hours.toFixed(1)}h daylight` : `${meta.label} unavailable`}
              className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-35 ${
                season === meta.key
                  ? "border-amber-300/60 bg-amber-300/15 text-amber-100"
                  : "border-ivory/15 text-ivory/65 hover:bg-ivory/5"
              }`}
            >
              {meta.shortLabel}
              {day && <span className="ml-1.5 font-normal text-ivory/40">{day.day_length_hours.toFixed(1)}h</span>}
            </button>
          );
        })}
      </div>

      {/* Scene + side panel */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-3">
          <SunArcScene
            days={sunPath.solstices_and_equinox}
            latitude={sunPath.latitude}
            longitude={sunPath.longitude}
            utcOffsetHours={utcOffset}
            season={season}
            timeMinutes={timeMinutes}
            elevation={position.elevation}
            azimuth={position.azimuth}
            showAllSeasons={showAllSeasons}
          />

          {/* Time scrubber */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3.5">
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => {
                  if (reducedMotion) return;
                  if (!playing && timeMinutes >= scrubRange.max) {
                    setTimeMinutes(scrubRange.min);
                  }
                  setPlaying((value) => !value);
                }}
                disabled={reducedMotion || !activeDay}
                title={reducedMotion ? "Animation disabled: reduced motion is on" : playing ? "Pause" : "Play the day"}
                className="inline-flex items-center gap-1.5 rounded-full bg-amber-300/90 px-3.5 py-1.5 text-xs font-semibold text-[#141b16] transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {playing ? <Pause aria-hidden="true" className="size-3.5" /> : <Play aria-hidden="true" className="size-3.5" />}
                {playing ? "Pause" : "Play day"}
              </button>
              <div className="text-right">
                <p className="font-mono text-lg font-semibold leading-none text-ivory">
                  {formatMinutesAsTime(timeMinutes)}
                </p>
                <p className="mt-1 text-[10px] text-ivory/45">
                  Elevation {position.elevation.toFixed(1)}° · Azimuth {position.azimuth.toFixed(0)}°
                </p>
              </div>
            </div>

            <input
              type="range"
              aria-label="Time of day"
              min={scrubRange.min}
              max={scrubRange.max}
              step={1}
              value={Math.round(timeMinutes)}
              onChange={(event) => {
                setPlaying(false);
                setTimeMinutes(Number(event.target.value));
              }}
              className="mt-3 w-full accent-amber-300"
            />
            <div className="mt-1 flex justify-between text-[10px] text-ivory/40">
              <span>{formatMinutesAsTime(scrubRange.min)}</span>
              <span className={`font-semibold ${inSun ? "text-amber-200" : "text-ivory/55"}`}>
                {facadeSunLabel(inSun, position.elevation)}
              </span>
              <span>{formatMinutesAsTime(scrubRange.max)}</span>
            </div>
            {reducedMotion && (
              <p className="mt-2 text-[10px] text-ivory/45">
                Reduced motion is on — scrub the slider to explore; autoplay is disabled.
              </p>
            )}
          </div>
        </div>

        {/* Right column: dial + score */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[0.65rem] font-semibold tracking-[0.18em] text-ivory/50 uppercase">
                  Facing / tower orientation
                </p>
                <p className="mt-1 text-xs text-ivory/60">
                  Tower <span className="font-semibold text-ivory">{towerLabel}</span> · {dialLabel}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setBearing(facingTextToBearing(unitFacingText) ?? 90)}
                title="Reset bearing"
                className="rounded-lg p-1.5 text-ivory/45 hover:bg-white/5 hover:text-ivory"
              >
                <RotateCcw aria-hidden="true" className="size-3.5" />
              </button>
            </div>

            <div className="mt-3">
              <FacingDial bearing={bearing} onChange={setBearing} />
            </div>

            <p className="mt-2 rounded-lg bg-white/[0.03] px-3 py-2 text-[11px] leading-relaxed text-ivory/60">
              {exposure === "morning" && "East sector — morning sun, cooler afternoons."}
              {exposure === "afternoon" && "West sector — strong afternoon sun and evening heat."}
              {exposure === "bright" && "South sector — bright, warm light most of the day."}
              {exposure === "diffused" && "North sector — cool, diffused light; minimal direct sun."}
            </p>

            {isAdmin && (
              <button
                type="button"
                onClick={handleSaveOrientation}
                disabled={orientationMutation.isPending}
                className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-ivory px-3 py-2 text-xs font-semibold text-[#141b16] transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {orientationMutation.isPending ? (
                  <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
                ) : (
                  <Save aria-hidden="true" className="size-3.5" />
                )}
                Save tower bearing
              </button>
            )}
            {saveNotice && <p role="status" className="mt-2 text-[11px] text-emerald-300">{saveNotice}</p>}
            {saveError && <p role="alert" className="mt-2 text-[11px] text-rose-300">{saveError}</p>}
          </div>

          {/* Unit score: prefer the server's confirmed score when the dial
              matches its bearing; otherwise show the live local preview. */}
          {unitId ? (
            unitScoreQuery.isLoading ? (
              <div role="status" className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-xs text-ivory/60">
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                Loading unit sun score…
              </div>
            ) : unitScoreQuery.isError ? (
              <div className="space-y-2">
                <SunScoreBadge score={localScore} isPreview />
                <p className="text-[11px] leading-relaxed text-ivory/50">
                  Server score unavailable ({errorMessage(unitScoreQuery.error, "no saved orientation")}). Showing the live preview for the dial bearing.
                </p>
              </div>
            ) : (
              <SunScoreBadge
                score={localScore}
                isPreview={
                  !unitScoreQuery.data ||
                  Math.round(unitScoreQuery.data.facing_bearing) !== Math.round(bearing)
                }
                loading={unitScoreQuery.isFetching}
              />
            )
          ) : (
            <SunScoreBadge score={localScore} isPreview />
          )}
        </div>
      </div>
    </div>
  );
}
