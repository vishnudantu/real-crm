// Solar-domain pure helpers ported from the backend FastAPI solar module.
// These mirror the Python implementations in backend/app/modules/solar so the
// client can animate sun position and preview facing scores without hammering
// the API during scrubbing. Field names match the Pydantic schemas exactly.

// ---------------------------------------------------------------------------
// API response shapes (backend/app/modules/solar/schemas.py)
// ---------------------------------------------------------------------------

export interface SunPathDay {
  date: string;
  sunrise: string;
  sunset: string;
  solar_noon: string;
  day_length_hours: number;
}

export interface SunPathResponse {
  project_id: string;
  latitude: number;
  longitude: number;
  solstices_and_equinox: SunPathDay[];
}

export interface UnitSunScoreResponse {
  unit_id: string;
  facing_bearing: number;
  facing_label: string;
  exposure_class: string;
  comfort_score: number;
  vastu_note: string;
  pricing_premium_min_pct: number;
  pricing_premium_max_pct: number;
  pricing_advisory: string;
}

export interface CoordinatesUpdateResponse {
  project_id: string;
  latitude: number;
  longitude: number;
}

export interface TowerOrientationResponse {
  id: string;
  project_id: string;
  tower_label: string;
  orientation_deg: number;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Compass (mirrors backend/app/modules/solar/compass.py)
// ---------------------------------------------------------------------------

export const COMPASS_LABELS = [
  "N", "NNE", "NE", "ENE",
  "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW",
  "W", "WNW", "NW", "NNW",
] as const;

export type CompassLabel = (typeof COMPASS_LABELS)[number];

const SECTOR_DEG = 360 / COMPASS_LABELS.length;

export function normalizeBearing(bearing: number): number {
  return ((bearing % 360) + 360) % 360;
}

export function bearingToCompass(bearing: number): CompassLabel {
  const normalized = normalizeBearing(bearing);
  const index = Math.floor((normalized + SECTOR_DEG / 2) / SECTOR_DEG) % COMPASS_LABELS.length;
  return COMPASS_LABELS[index];
}

export const COMPASS_FULL_NAMES: Readonly<Record<CompassLabel, string>> = {
  N: "North", NNE: "North-northeast", NE: "Northeast", ENE: "East-northeast",
  E: "East", ESE: "East-southeast", SE: "Southeast", SSE: "South-southeast",
  S: "South", SSW: "South-southwest", SW: "Southwest", WSW: "West-southwest",
  W: "West", WNW: "West-northwest", NW: "Northwest", NNW: "North-northwest",
};

/** Parse free-text unit facing (e.g. "East", "North East", "E", "90") into a
 *  bearing, or null if it cannot be determined. */
export function facingTextToBearing(text: string | null | undefined): number | null {
  if (!text) return null;
  const trimmed = text.trim();
  const numeric = Number(trimmed);
  if (trimmed && Number.isFinite(numeric)) return normalizeBearing(numeric);
  const normalized = trimmed.toUpperCase().replace(/[\s_-]+/g, "");
  const index = (COMPASS_LABELS as readonly string[]).indexOf(normalized);
  if (index >= 0) return index * SECTOR_DEG;
  // Common long-hand spellings.
  const longMap: Record<string, number> = {
    NORTH: 0, EAST: 90, SOUTH: 180, WEST: 270,
    NORTHEAST: 45, SOUTHEAST: 135, SOUTHWEST: 225, NORTHWEST: 315,
  };
  const value = longMap[normalized];
  return value === undefined ? null : value;
}

// ---------------------------------------------------------------------------
// NOAA solar position (mirrors backend/app/modules/solar/engine.py)
// ---------------------------------------------------------------------------

export interface SolarPosition {
  elevation: number;
  azimuth: number;
}

const DEG = Math.PI / 180;

/** Local-civil-time description of an instant, plus its UTC offset in hours.
 *  The backend computes in UTC (offset 0); callers supply the offset so the
 *  animation can display local times for the site. */
export interface LocalDateTime {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  utcOffsetHours: number;
}

function fractionalYear(when: LocalDateTime): number {
  const dayOfYear = dayOfYearFor(when.year, when.month, when.day);
  const hour = when.hour + when.minute / 60 + when.second / 3600;
  return ((2 * Math.PI) / 365) * (dayOfYear - 1 + (hour - 12) / 24);
}

function dayOfYearFor(year: number, month: number, day: number): number {
  const start = Date.UTC(year, 0, 1);
  const current = Date.UTC(year, month - 1, day);
  return Math.round((current - start) / 86_400_000) + 1;
}

function equationOfTime(gamma: number): number {
  return (
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(gamma) -
      0.032077 * Math.sin(gamma) -
      0.014615 * Math.cos(2 * gamma) -
      0.040849 * Math.sin(2 * gamma))
  );
}

function solarDeclination(gamma: number): number {
  return (
    0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma) -
    0.002697 * Math.cos(3 * gamma) +
    0.00148 * Math.sin(3 * gamma)
  );
}

/** Compute solar elevation (degrees above horizon) and azimuth (degrees
 *  clockwise from north) for an instant expressed in site-local time. */
export function solarPosition(
  latitude: number,
  longitude: number,
  when: LocalDateTime,
): SolarPosition {
  const gamma = fractionalYear(when);
  const eqTime = equationOfTime(gamma);
  const decl = solarDeclination(gamma);

  const trueSolarTime =
    ((when.hour * 60 +
      when.minute +
      when.second / 60 +
      eqTime +
      4 * longitude -
      60 * when.utcOffsetHours) %
      1440 +
      1440) %
    1440;

  const haDeg = trueSolarTime / 4 - 180;
  const haRad = haDeg * DEG;
  const latRad = latitude * DEG;

  let cosZenith =
    Math.sin(latRad) * Math.sin(decl) +
    Math.cos(latRad) * Math.cos(decl) * Math.cos(haRad);
  cosZenith = Math.max(-1, Math.min(1, cosZenith));
  const zenith = Math.acos(cosZenith);
  const elevation = 90 - zenith / DEG;

  const azDenom = Math.cos(latRad) * Math.sin(zenith);
  let azimuth: number;
  if (Math.abs(azDenom) < 1e-12) {
    azimuth = 180;
  } else {
    let cosAz = -(Math.sin(latRad) * cosZenith - Math.sin(decl)) / azDenom;
    cosAz = Math.max(-1, Math.min(1, cosAz));
    azimuth = Math.acos(cosAz) / DEG;
    if (haRad > 0) azimuth = 360 - azimuth;
  }
  return { elevation, azimuth };
}

/** Derive a LocalDateTime at a site from an ISO datetime string (as returned by
 *  the backend) plus an explicit UTC offset (e.g. 5.5 for IST). The backend
 *  returns UTC ISO strings; we shift to site-local civil time so the scrubber
 *  shows wall-clock times buyers recognise. */
export function isoToLocal(iso: string, utcOffsetHours: number): LocalDateTime {
  const date = new Date(iso);
  const shifted = new Date(date.getTime() + utcOffsetHours * 3_600_000);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
    second: shifted.getUTCSeconds(),
    utcOffsetHours,
  };
}

export function localToMinutes(when: LocalDateTime): number {
  return when.hour * 60 + when.minute + when.second / 60;
}

export function minutesToLocalTime(
  minutes: number,
  base: LocalDateTime,
): LocalDateTime {
  const wrapped = ((minutes % 1440) + 1440) % 1440;
  const hour = Math.floor(wrapped / 60);
  const minuteFloat = wrapped - hour * 60;
  const minute = Math.floor(minuteFloat);
  const second = Math.round((minuteFloat - minute) * 60);
  return { ...base, hour, minute, second };
}

/** Format minutes-from-midnight as "6:24 AM". */
export function formatMinutesAsTime(minutes: number): string {
  const wrapped = ((minutes % 1440) + 1440) % 1440;
  let hour = Math.floor(wrapped / 60);
  const minute = Math.floor(wrapped % 60);
  const suffix = hour < 12 ? "AM" : "PM";
  hour = hour % 12;
  if (hour === 0) hour = 12;
  return `${hour}:${String(minute).padStart(2, "0")} ${suffix}`;
}

// ---------------------------------------------------------------------------
// Scoring (mirrors backend/app/modules/solar/scoring.py)
// ---------------------------------------------------------------------------

export type ExposureClass = "morning" | "afternoon" | "diffused" | "bright";

export interface SunScore {
  facing_bearing: number;
  facing_label: CompassLabel;
  exposure_class: ExposureClass;
  comfort_score: number;
  vastu_note: string;
  pricing_premium_min_pct: number;
  pricing_premium_max_pct: number;
  pricing_advisory: string;
}

export function classifyExposure(bearing: number): ExposureClass {
  const normalized = normalizeBearing(bearing);
  if (normalized >= 45 && normalized < 135) return "morning";
  if (normalized >= 135 && normalized < 225) return "bright";
  if (normalized >= 225 && normalized < 315) return "afternoon";
  return "diffused";
}

const BASE_COMFORT: Readonly<Record<ExposureClass, number>> = {
  morning: 85,
  diffused: 75,
  bright: 60,
  afternoon: 40,
};

function isCornerLabel(label: string): boolean {
  return label.length >= 2 && !["N", "E", "S", "W"].includes(label);
}

const VASTU_NOTES: Readonly<Record<ExposureClass, string>> = {
  morning:
    "East-facing units are traditionally preferred in Vastu Shastra for morning sunlight and positive energy flow.",
  diffused:
    "North-facing units are traditionally preferred in Vastu Shastra for cool, diffused light throughout the day.",
  bright:
    "South-facing units receive bright, warm light. In Vastu Shastra, south-facing is generally acceptable but may need shading in summer.",
  afternoon:
    "West-facing units receive strong afternoon sun. In Vastu Shastra, west and south-west orientations traditionally require care — consider shading and ventilation.",
};

const PREMIUM_RANGES: Readonly<Record<ExposureClass, [number, number]>> = {
  morning: [3, 7],
  diffused: [1, 4],
  bright: [0, 2],
  afternoon: [-2, 0],
};

export function scoreUnitFacing(bearing: number): SunScore {
  const normalized = normalizeBearing(bearing);
  const label = bearingToCompass(normalized);
  const exposure = classifyExposure(normalized);
  const bonus = isCornerLabel(label) ? 5 : 0;
  const comfort = Math.min(100, BASE_COMFORT[exposure] + bonus);
  let note = VASTU_NOTES[exposure];
  let [minPct, maxPct] = PREMIUM_RANGES[exposure];
  if (isCornerLabel(label)) {
    note += " Corner orientation adds cross-ventilation benefit.";
    minPct += 1;
    maxPct += 2;
  }
  const advisory = `Advisory premium: ${minPct >= 0 ? "+" : ""}${minPct.toFixed(0)}% to ${maxPct >= 0 ? "+" : ""}${maxPct.toFixed(0)}%. This is approximate and should be validated against local market data.`;
  return {
    facing_bearing: normalized,
    facing_label: label,
    exposure_class: exposure,
    comfort_score: comfort,
    vastu_note: note,
    pricing_premium_min_pct: minPct,
    pricing_premium_max_pct: maxPct,
    pricing_advisory: advisory,
  };
}

// ---------------------------------------------------------------------------
// Presentation helpers (score → label / tone)
// ---------------------------------------------------------------------------

export type ScoreTone = "emerald" | "amber" | "sky" | "rose";

export interface ExposureVisual {
  label: string;
  description: string;
  tone: ScoreTone;
}

export const EXPOSURE_VISUALS: Readonly<Record<ExposureClass, ExposureVisual>> = {
  morning: {
    label: "Morning sun",
    description: "Gentle east light, cooler afternoons",
    tone: "emerald",
  },
  afternoon: {
    label: "Afternoon heat",
    description: "Strong west sun, warmer evenings",
    tone: "rose",
  },
  diffused: {
    label: "Diffused light",
    description: "Cool, even north light all day",
    tone: "sky",
  },
  bright: {
    label: "Bright & warm",
    description: "Strong south light, warm in summer",
    tone: "amber",
  },
};

export function comfortTone(score: number): ScoreTone {
  if (score >= 80) return "emerald";
  if (score >= 65) return "sky";
  if (score >= 50) return "amber";
  return "rose";
}

// ---------------------------------------------------------------------------
// Facade direct-sun model (geometric)
// ---------------------------------------------------------------------------

/** Whether a facade with outward-normal `facadeBearing` (degrees clockwise from
 *  north) receives direct sunlight when the sun sits at `sunAzimuth` with
 *  `sunElevation`. A facade is lit when the sun is above the horizon and within
 *  90° of the facade's outward normal (dot product positive). */
export function isFacadeInSun(
  facadeBearing: number,
  sunAzimuth: number,
  sunElevation: number,
): boolean {
  if (sunElevation <= 0) return false;
  const diff = normalizeBearing(sunAzimuth - facadeBearing);
  const angle = diff > 180 ? 360 - diff : diff;
  return angle < 90;
}

/** Human label for the scrubber readout. */
export function facadeSunLabel(inSun: boolean, sunElevation: number): string {
  if (sunElevation <= 0) return "Night — sun below horizon";
  return inSun ? "Direct sun on this facade" : "Shade — sun behind this facade";
}

// ---------------------------------------------------------------------------
// Seasons
// ---------------------------------------------------------------------------

export type SeasonKey = "summer" | "equinox" | "winter";

export interface SeasonMeta {
  key: SeasonKey;
  label: string;
  shortLabel: string;
  /** Substring that identifies the representative date in the backend payload. */
  dateFragment: string;
}

export const SEASONS: readonly SeasonMeta[] = [
  { key: "summer", label: "Summer solstice", shortLabel: "Summer", dateFragment: "06-21" },
  { key: "equinox", label: "Vernal equinox", shortLabel: "Equinox", dateFragment: "03-20" },
  { key: "winter", label: "Winter solstice", shortLabel: "Winter", dateFragment: "12-21" },
];

/** Pick the SunPathDay matching a season from the API payload. Falls back to
 *  the autumnal equinox for the equinox slot if the vernal entry is missing. */
export function dayForSeason(
  days: readonly SunPathDay[],
  season: SeasonKey,
): SunPathDay | null {
  const fragment = SEASONS.find((s) => s.key === season)?.dateFragment;
  if (!fragment) return null;
  const match = days.find((d) => d.date.includes(fragment));
  if (match) return match;
  if (season === "equinox") {
    return days.find((d) => d.date.includes("09-22")) ?? null;
  }
  return null;
}

/** Default UTC offset suggestion from longitude (15° ≈ 1 hour), snapped to the
 *  half-hour grid used by real timezones. Callers may override explicitly
 *  (India = 5.5). */
export function suggestUtcOffset(longitude: number): number {
  return Math.round((longitude / 15) * 2) / 2;
}
