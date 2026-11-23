import { motion, useReducedMotion } from "framer-motion";
import { CloudSun, Flame, Sun, Sunrise } from "lucide-react";
import { EXPOSURE_VISUALS } from "./solarModel";
import type { ExposureClass, ScoreTone, SunScore } from "./solarModel";

const EXPOSURE_ICONS: Record<ExposureClass, typeof Sunrise> = {
  morning: Sunrise,
  afternoon: Flame,
  diffused: CloudSun,
  bright: Sun,
};

const TONE_TEXT: Record<ScoreTone, string> = {
  emerald: "text-emerald-300",
  amber: "text-amber-300",
  sky: "text-sky-300",
  rose: "text-rose-300",
};

const TONE_STROKE: Record<ScoreTone, string> = {
  emerald: "#5fbf8f",
  amber: "#e5b85c",
  sky: "#7fb3d5",
  rose: "#e08a80",
};

const TONE_BADGE: Record<ScoreTone, string> = {
  emerald: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-400/25 bg-amber-400/10 text-amber-200",
  sky: "border-sky-400/25 bg-sky-400/10 text-sky-200",
  rose: "border-rose-400/25 bg-rose-400/10 text-rose-200",
};

interface SunScoreBadgeProps {
  score: SunScore;
  /** True when the displayed score is a local preview rather than a
   *  server-confirmed value for the saved orientation. */
  isPreview?: boolean;
  loading?: boolean;
}

const GAUGE_RADIUS = 52;
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS;

export function SunScoreBadge({ score, isPreview = false, loading = false }: SunScoreBadgeProps) {
  const reduceMotion = useReducedMotion();
  const visual = EXPOSURE_VISUALS[score.exposure_class];
  const Icon = EXPOSURE_ICONS[score.exposure_class];
  const tone = visual.tone;
  const dash = (score.comfort_score / 100) * GAUGE_CIRCUMFERENCE;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[0.65rem] font-semibold tracking-[0.18em] text-ivory/50 uppercase">
          Unit sun score
        </p>
        {isPreview && (
          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[10px] font-medium text-ivory/60">
            Live preview
          </span>
        )}
      </div>

      <div className="mt-3 flex items-center gap-4">
        {/* Radial gauge */}
        <div className="relative shrink-0">
          <svg width={128} height={128} viewBox="0 0 128 128" role="img" aria-label={`Comfort score ${score.comfort_score} out of 100`}>
            <circle
              cx={64}
              cy={64}
              r={GAUGE_RADIUS}
              fill="none"
              stroke="#f5f2eb"
              strokeOpacity={0.1}
              strokeWidth={9}
            />
            <motion.circle
              cx={64}
              cy={64}
              r={GAUGE_RADIUS}
              fill="none"
              stroke={TONE_STROKE[tone]}
              strokeWidth={9}
              strokeLinecap="round"
              strokeDasharray={GAUGE_CIRCUMFERENCE}
              transform="rotate(-90 64 64)"
              initial={reduceMotion ? false : { strokeDashoffset: GAUGE_CIRCUMFERENCE }}
              animate={{ strokeDashoffset: GAUGE_CIRCUMFERENCE - dash }}
              transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 60, damping: 16 }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-3xl font-semibold tracking-tight ${TONE_TEXT[tone]}`}>
              {score.comfort_score}
            </span>
            <span className="text-[10px] font-medium tracking-wide text-ivory/45">/ 100 comfort</span>
          </div>
        </div>

        {/* Exposure class */}
        <div className="min-w-0 flex-1">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${TONE_BADGE[tone]}`}>
            <Icon aria-hidden="true" className="size-3.5" />
            {visual.label}
          </span>
          <p className="mt-2 text-xs leading-relaxed text-ivory/60">{visual.description}</p>
          <p className="mt-1.5 text-xs text-ivory/75">
            Facing <span className="font-semibold text-ivory">{score.facing_label}</span>
            <span className="text-ivory/40"> · {Math.round(score.facing_bearing)}°</span>
          </p>
        </div>
      </div>

      {/* Vastu note */}
      <div className="mt-4 border-t border-white/10 pt-3">
        <p className="text-[0.62rem] font-semibold tracking-[0.16em] text-ivory/45 uppercase">Vastu note</p>
        <p className="mt-1 text-[11px] leading-relaxed text-ivory/70">{score.vastu_note}</p>
      </div>

      {/* Pricing advisory */}
      <div className="mt-3 flex items-start justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5">
        <div>
          <p className="text-[0.62rem] font-semibold tracking-[0.16em] text-ivory/45 uppercase">
            Pricing hint <span className="normal-case text-ivory/35">(advisory)</span>
          </p>
          <p className="mt-0.5 text-sm font-semibold text-ivory">
            {score.pricing_premium_min_pct >= 0 ? "+" : ""}
            {score.pricing_premium_min_pct}% to {score.pricing_premium_max_pct >= 0 ? "+" : ""}
            {score.pricing_premium_max_pct}%
          </p>
        </div>
        <p className="max-w-[45%] text-right text-[10px] leading-snug text-ivory/45">
          Approximate. Validate against local market data.
        </p>
      </div>

      {loading && (
        <p role="status" className="mt-2 text-[11px] text-ivory/50">Refreshing server score…</p>
      )}
    </div>
  );
}
