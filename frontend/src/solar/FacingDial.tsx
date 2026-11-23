import { useCallback, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { COMPASS_LABELS, normalizeBearing } from "./solarModel";

interface FacingDialProps {
  bearing: number;
  onChange: (bearing: number) => void;
  disabled?: boolean;
  /** Show morning/afternoon sun sectors as coloured arcs. */
  showSectors?: boolean;
}

const SIZE = 240;
const CENTER = SIZE / 2;
const RADIUS = 92;
const TICK_OUTER = RADIUS + 6;
const LABEL_RADIUS = RADIUS + 20;

function polarToXY(deg: number, radius: number): { x: number; y: number } {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: CENTER + radius * Math.cos(rad), y: CENTER + radius * Math.sin(rad) };
}

export function FacingDial({ bearing, onChange, disabled = false, showSectors = true }: FacingDialProps) {
  const reduceMotion = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState(false);

  const bearingFromPointer = useCallback((clientX: number, clientY: number): number => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return 0;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
    const deg = (Math.atan2(dx, -dy) * 180) / Math.PI;
    return Math.round(normalizeBearing(deg));
  }, []);

  const handlePointer = (event: React.PointerEvent<SVGSVGElement>) => {
    if (disabled) return;
    onChange(bearingFromPointer(event.clientX, event.clientY));
  };

  const startDrag = (event: React.PointerEvent<SVGSVGElement>) => {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
    handlePointer(event);
  };

  const endDrag = () => setDragging(false);

  const needle = polarToXY(bearing, RADIUS - 12);
  const tail = polarToXY(bearing + 180, 26);

  // Morning sector: 45°–135° (east), afternoon: 225°–315° (west).
  const sectorArc = (from: number, to: number): string => {
    const start = polarToXY(from, RADIUS - 2);
    const end = polarToXY(to, RADIUS - 2);
    const largeArc = to - from > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${RADIUS - 2} ${RADIUS - 2} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  };

  return (
    <div className="flex flex-col items-center">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className={`h-auto w-full max-w-[240px] touch-none select-none ${disabled ? "opacity-50" : "cursor-grab active:cursor-grabbing"}`}
        role="slider"
        aria-label="Tower facing bearing"
        aria-valuemin={0}
        aria-valuemax={359}
        aria-valuenow={Math.round(bearing)}
        aria-valuetext={`${Math.round(bearing)} degrees`}
        tabIndex={disabled ? -1 : 0}
        onPointerDown={startDrag}
        onPointerMove={(event) => {
          if (dragging) handlePointer(event);
        }}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={(event) => {
          if (disabled) return;
          const step = event.shiftKey ? 22.5 : 1;
          if (event.key === "ArrowRight" || event.key === "ArrowUp") {
            event.preventDefault();
            onChange(normalizeBearing(Math.round(bearing + step)));
          } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
            event.preventDefault();
            onChange(normalizeBearing(Math.round(bearing - step)));
          }
        }}
      >
        <defs>
          <radialGradient id="dial-face" cx="50%" cy="42%" r="65%">
            <stop offset="0%" stopColor="#2b352c" />
            <stop offset="100%" stopColor="#181f19" />
          </radialGradient>
        </defs>

        <circle cx={CENTER} cy={CENTER} r={RADIUS + 8} fill="url(#dial-face)" stroke="#f5f2eb" strokeOpacity={0.12} />

        {/* Morning / afternoon sectors */}
        {showSectors && (
          <g fill="none" strokeWidth={5} strokeLinecap="round" opacity={0.5}>
            <path d={sectorArc(45, 135)} stroke="#f4c168" />
            <path d={sectorArc(225, 315)} stroke="#e08a6d" />
          </g>
        )}

        {/* Ticks and labels */}
        {COMPASS_LABELS.map((label, index) => {
          const deg = index * 22.5;
          const isCardinal = index % 4 === 0;
          const isOrdinal = index % 2 === 0;
          const outer = polarToXY(deg, TICK_OUTER);
          const inner = polarToXY(deg, isCardinal ? TICK_OUTER - 12 : TICK_OUTER - 7);
          const labelPos = polarToXY(deg, LABEL_RADIUS);
          return (
            <g key={label}>
              <line
                x1={inner.x}
                y1={inner.y}
                x2={outer.x}
                y2={outer.y}
                stroke="#f5f2eb"
                strokeOpacity={isCardinal ? 0.85 : 0.35}
                strokeWidth={isCardinal ? 2 : 1}
              />
              {(isCardinal || isOrdinal) && (
                <text
                  x={labelPos.x}
                  y={labelPos.y}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="#f5f2eb"
                  fillOpacity={isCardinal ? 0.95 : 0.55}
                  fontSize={isCardinal ? 14 : 10}
                  fontWeight={isCardinal ? 700 : 500}
                >
                  {label}
                </text>
              )}
            </g>
          );
        })}

        {/* Needle */}
        <motion.g
          animate={{ rotate: bearing }}
          transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 160, damping: 18 }}
          style={{ originX: `${CENTER}px`, originY: `${CENTER}px` }}
        >
          <line
            x1={CENTER}
            y1={CENTER}
            x2={CENTER}
            y2={CENTER - (RADIUS - 16)}
            stroke="#ffd977"
            strokeWidth={3}
            strokeLinecap="round"
          />
          <polygon
            points={`${CENTER},${CENTER - (RADIUS - 6)} ${CENTER - 7},${CENTER - (RADIUS - 26)} ${CENTER + 7},${CENTER - (RADIUS - 26)}`}
            fill="#ffd977"
          />
        </motion.g>
        <line x1={tail.x} y1={tail.y} x2={CENTER} y2={CENTER} stroke="#f5f2eb" strokeOpacity={0.25} strokeWidth={2} />
        <line x1={CENTER} y1={CENTER} x2={needle.x} y2={needle.y} stroke="transparent" strokeWidth={0} />

        {/* Hub */}
        <circle cx={CENTER} cy={CENTER} r={7} fill="#202923" stroke="#ffd977" strokeWidth={2} />
      </svg>

      {/* Readout */}
      <div className="mt-2 text-center">
        <p className="font-mono text-2xl font-semibold tracking-tight text-ivory">
          {Math.round(bearing)}°
        </p>
        <p className="text-[11px] font-medium tracking-wide text-ivory/55">
          {disabled ? "Facing unavailable" : dragging ? "Release to set bearing" : "Drag or use arrow keys"}
        </p>
      </div>
    </div>
  );
}
