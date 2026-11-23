import { useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  isoToLocal,
  localToMinutes,
  solarPosition,
  formatMinutesAsTime,
  dayForSeason,
  SEASONS,
} from "./solarModel";
import type { SeasonKey, SunPathDay } from "./solarModel";

export interface SeasonArc {
  season: SeasonKey;
  label: string;
  color: string;
  /** SVG path for this season's sun arc, or null if the day has no data. */
  path: string | null;
  dayLengthHours: number | null;
}

interface SunArcSceneProps {
  days: readonly SunPathDay[];
  latitude: number;
  longitude: number;
  utcOffsetHours: number;
  season: SeasonKey;
  /** Minutes from local midnight currently scrubbed to. */
  timeMinutes: number;
  /** Elevation/azimuth of the active-season sun at timeMinutes. */
  elevation: number;
  azimuth: number;
  showAllSeasons: boolean;
}

const WIDTH = 720;
const HEIGHT = 340;
const HORIZON_Y = 268;
const LEFT_X = 60;
const RIGHT_X = WIDTH - 60;
const PEAK_Y = 52;

const SEASON_COLORS: Record<SeasonKey, string> = {
  summer: "#f4a261",
  equinox: "#8fd3a7",
  winter: "#7fb3d5",
};

/** Sky gradient stops shift with the sun's elevation to evoke dawn/noon/dusk/night. */
function skyPalette(elevation: number): { top: string; mid: string; bottom: string; label: string } {
  if (elevation <= -8) {
    return { top: "#0b1026", mid: "#141a33", bottom: "#1d2540", label: "Night" };
  }
  if (elevation <= 0) {
    return { top: "#1b2242", mid: "#4b3a5a", bottom: "#b4665a", label: "Twilight" };
  }
  if (elevation <= 12) {
    return { top: "#2c3a5e", mid: "#c0755a", bottom: "#f2b263", label: "Golden hour" };
  }
  if (elevation <= 35) {
    return { top: "#2f4a73", mid: "#7d8fa6", bottom: "#e8c98f", label: "Morning" };
  }
  return { top: "#33517d", mid: "#8fa9bf", bottom: "#f4e3b8", label: "Midday" };
}

function arcPoint(
  t: number,
  maxElevation: number,
): { x: number; y: number } {
  // t in [0,1] from sunrise to sunset. Height scales with the season's peak
  // elevation so winter arcs read visibly lower than summer arcs.
  const x = LEFT_X + (RIGHT_X - LEFT_X) * t;
  const elevationRatio = Math.max(0.06, Math.min(1, maxElevation / 90));
  const amplitude = (HORIZON_Y - PEAK_Y) * elevationRatio;
  const y = HORIZON_Y - Math.sin(Math.PI * t) * amplitude;
  return { x, y };
}

function buildArcPath(maxElevation: number): string {
  const points = 48;
  let d = "";
  for (let i = 0; i <= points; i += 1) {
    const { x, y } = arcPoint(i / points, maxElevation);
    d += `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)} `;
  }
  return d.trim();
}

/** Interpolate along the drawn arc using the same parameterisation. */
function sunPositionOnArc(
  timeMinutes: number,
  day: SunPathDay | null,
  utcOffsetHours: number,
  maxElevation: number,
): { x: number; y: number; visible: boolean } {
  if (!day) return { x: WIDTH / 2, y: HORIZON_Y, visible: false };
  const sunrise = localToMinutes(isoToLocal(day.sunrise, utcOffsetHours));
  const sunset = localToMinutes(isoToLocal(day.sunset, utcOffsetHours));
  const span = Math.max(1, sunset - sunrise);
  const t = (timeMinutes - sunrise) / span;
  if (t < 0 || t > 1) {
    // Below the horizon: park the sun just under the nearest end of the arc.
    const clamped = Math.max(0, Math.min(1, t));
    const { x } = arcPoint(clamped, maxElevation);
    return { x, y: HORIZON_Y + 26, visible: false };
  }
  const { x, y } = arcPoint(t, maxElevation);
  return { x, y, visible: true };
}

export function SunArcScene({
  days,
  latitude,
  longitude,
  utcOffsetHours,
  season,
  timeMinutes,
  elevation,
  azimuth,
  showAllSeasons,
}: SunArcSceneProps) {
  const reduceMotion = useReducedMotion();

  // Compute each season's peak elevation (at its solar noon) once per data load.
  const seasonData = useMemo(() => {
    return SEASONS.map((meta) => {
      const day = dayForSeason(days, meta.key);
      let maxElevation = 60;
      let noonMinutes = 720;
      if (day) {
        const noonLocal = isoToLocal(day.solar_noon, utcOffsetHours);
        noonMinutes = localToMinutes(noonLocal);
        const pos = solarPosition(latitude, longitude, noonLocal);
        maxElevation = Math.max(4, pos.elevation);
      }
      return {
        meta,
        day,
        maxElevation,
        noonMinutes,
        path: day ? buildArcPath(maxElevation) : null,
        color: SEASON_COLORS[meta.key],
      };
    });
  }, [days, latitude, longitude, utcOffsetHours]);

  const active = seasonData.find((s) => s.meta.key === season) ?? seasonData[0];
  const activeDay = active.day;
  const sun = sunPositionOnArc(timeMinutes, activeDay, utcOffsetHours, active.maxElevation);

  const palette = skyPalette(elevation);
  const isNight = elevation <= 0;
  const noonPoint = arcPoint(0.5, active.maxElevation);

  const sunriseLabel = activeDay
    ? formatMinutesAsTime(localToMinutes(isoToLocal(activeDay.sunrise, utcOffsetHours)))
    : "—";
  const sunsetLabel = activeDay
    ? formatMinutesAsTime(localToMinutes(isoToLocal(activeDay.sunset, utcOffsetHours)))
    : "—";
  const noonLabel = activeDay
    ? formatMinutesAsTime(localToMinutes(isoToLocal(activeDay.solar_noon, utcOffsetHours)))
    : "—";

  // Deterministic star field for the night sky.
  const stars = useMemo(() => {
    const result: { x: number; y: number; r: number; o: number }[] = [];
    let seed = 42;
    for (let i = 0; i < 46; i += 1) {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      const rx = seed / 2147483648;
      seed = (seed * 1103515245 + 12345) % 2147483648;
      const ry = seed / 2147483648;
      seed = (seed * 1103515245 + 12345) % 2147483648;
      const ro = seed / 2147483648;
      result.push({
        x: 20 + rx * (WIDTH - 40),
        y: 16 + ry * (HORIZON_Y - 60),
        r: 0.6 + ro * 1.1,
        o: 0.25 + ro * 0.5,
      });
    }
    return result;
  }, []);

  const gradientId = `sky-${season}`;
  const glowId = `sun-glow-${season}`;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 shadow-lg">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="block h-auto w-full"
        role="img"
        aria-label={`Sun path for ${active.meta.label}. Sunrise ${sunriseLabel}, solar noon ${noonLabel}, sunset ${sunsetLabel}.`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={palette.top} />
            <stop offset="55%" stopColor={palette.mid} />
            <stop offset="100%" stopColor={palette.bottom} />
          </linearGradient>
          <radialGradient id={glowId} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff7d6" stopOpacity="0.95" />
            <stop offset="35%" stopColor="#ffd977" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ffb347" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`ground-${season}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1c2420" />
            <stop offset="100%" stopColor="#10150f" />
          </linearGradient>
        </defs>

        {/* Sky */}
        <rect x="0" y="0" width={WIDTH} height={HORIZON_Y} fill={`url(#${gradientId})`} />

        {/* Stars at night */}
        <g opacity={isNight ? 1 : 0} style={{ transition: reduceMotion ? undefined : "opacity 700ms ease" }}>
          {stars.map((star, index) => (
            <circle key={index} cx={star.x} cy={star.y} r={star.r} fill="#f5f2eb" opacity={star.o} />
          ))}
        </g>

        {/* Ground */}
        <rect x="0" y={HORIZON_Y} width={WIDTH} height={HEIGHT - HORIZON_Y} fill={`url(#ground-${season})`} />

        {/* All-season overlay arcs (dimmed) */}
        {showAllSeasons &&
          seasonData.map((s) =>
            s.path && s.meta.key !== season ? (
              <path
                key={s.meta.key}
                d={s.path}
                fill="none"
                stroke={s.color}
                strokeWidth={1.5}
                strokeDasharray="3 6"
                opacity={0.4}
                strokeLinecap="round"
              />
            ) : null,
          )}

        {/* Active season arc */}
        {active.path && (
          <motion.path
            d={active.path}
            fill="none"
            stroke={active.color}
            strokeWidth={2.5}
            strokeLinecap="round"
            initial={reduceMotion ? false : { pathLength: 0, opacity: 0.4 }}
            animate={{ pathLength: 1, opacity: 0.95 }}
            transition={{ duration: reduceMotion ? 0 : 1.1, ease: "easeInOut" }}
          />
        )}

        {/* Horizon line */}
        <line
          x1={0}
          y1={HORIZON_Y}
          x2={WIDTH}
          y2={HORIZON_Y}
          stroke="#f5f2eb"
          strokeOpacity={0.35}
          strokeWidth={1}
        />

        {/* Solar-noon marker */}
        {activeDay && (
          <g>
            <line
              x1={noonPoint.x}
              y1={noonPoint.y - 6}
              x2={noonPoint.x}
              y2={HORIZON_Y}
              stroke="#f5f2eb"
              strokeOpacity={0.28}
              strokeDasharray="2 5"
            />
            <circle cx={noonPoint.x} cy={noonPoint.y} r={3} fill="#fff7d6" opacity={0.8} />
            <text
              x={noonPoint.x}
              y={noonPoint.y - 12}
              textAnchor="middle"
              fill="#f5f2eb"
              fillOpacity={0.8}
              fontSize={10}
              fontFamily="inherit"
            >
              Solar noon {noonLabel}
            </text>
          </g>
        )}

        {/* Sunrise / sunset labels */}
        <text x={LEFT_X} y={HORIZON_Y + 20} textAnchor="middle" fill="#f5f2eb" fillOpacity={0.7} fontSize={10}>
          {sunriseLabel}
        </text>
        <text x={LEFT_X} y={HORIZON_Y + 33} textAnchor="middle" fill="#f5f2eb" fillOpacity={0.45} fontSize={9}>
          Sunrise
        </text>
        <text x={RIGHT_X} y={HORIZON_Y + 20} textAnchor="middle" fill="#f5f2eb" fillOpacity={0.7} fontSize={10}>
          {sunsetLabel}
        </text>
        <text x={RIGHT_X} y={HORIZON_Y + 33} textAnchor="middle" fill="#f5f2eb" fillOpacity={0.45} fontSize={9}>
          Sunset
        </text>

        {/* Compass direction hint on the arc */}
        <text x={WIDTH / 2} y={HEIGHT - 10} textAnchor="middle" fill="#f5f2eb" fillOpacity={0.4} fontSize={9}>
          East → South → West · sun azimuth {azimuth.toFixed(0)}° · elevation {elevation.toFixed(1)}°
        </text>

        {/* The sun */}
        <motion.g
          animate={{ x: sun.x, y: sun.y }}
          transition={
            reduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 120, damping: 20, mass: 0.6 }
          }
          style={{ opacity: sun.visible ? 1 : 0.35 }}
        >
          <circle cx={0} cy={0} r={44} fill={`url(#${glowId})`} opacity={sun.visible ? 0.9 : 0.3} />
          <circle cx={0} cy={0} r={13} fill={sun.visible ? "#ffdf8a" : "#8b93a7"} />
          <circle cx={0} cy={0} r={13} fill="none" stroke="#fff7d6" strokeOpacity={0.7} strokeWidth={1} />
        </motion.g>

        {/* Sky-phase caption */}
        <text x={16} y={26} fill="#f5f2eb" fillOpacity={0.75} fontSize={11} fontWeight={600}>
          {palette.label}
        </text>
      </svg>
    </div>
  );
}
