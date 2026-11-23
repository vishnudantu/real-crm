import { useMemo, useState } from "react";
import type { CollectionsSeriesPoint } from "./executiveModel";
import { formatPaise } from "./executiveModel";

interface CollectionsChartProps {
  series: CollectionsSeriesPoint[];
}

const CHART_HEIGHT = 200;
const PADDING_LEFT = 56;
const PADDING_RIGHT = 12;
const PADDING_TOP = 14;
const PADDING_BOTTOM = 28;

/** Monthly live-receipt collections as a single-series bar chart (INR axis). */
export function CollectionsChart({ series }: CollectionsChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  const { max, ticks } = useMemo(() => {
    const rawMax = series.reduce((acc, p) => Math.max(acc, p.collectedPaise), 0);
    // Axis in ₹ lakhs for readability when values are large.
    if (rawMax === 0) return { max: 4, ticks: [0, 1, 2, 3, 4] };
    const magnitude = 10 ** Math.floor(Math.log10(rawMax));
    const step = magnitude / 2;
    const max = Math.ceil(rawMax / step) * step;
    const ticks: number[] = [];
    for (let v = 0; v <= max; v += step) ticks.push(v);
    return { max, ticks };
  }, [series]);

  const total = series.reduce((acc, p) => acc + p.collectedPaise, 0);

  if (series.length === 0 || total === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-charcoal/20 bg-[#FAFAF7] p-6 text-center">
        <p className="text-sm font-semibold text-charcoal">No collections in this window</p>
        <p className="mt-1 text-xs text-charcoal/55">
          Live receipts (voided entries excluded) will chart here by month.
        </p>
      </div>
    );
  }

  const width = Math.max(560, series.length * 52);
  const innerWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const innerHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const baseY = PADDING_TOP + innerHeight;
  const slot = innerWidth / series.length;
  const barWidth = Math.max(10, Math.min(28, slot * 0.5));
  const yFor = (value: number) => baseY - (value / max) * innerHeight;
  const hoveredPoint = hovered !== null ? series[hovered] : null;

  return (
    <div>
      {hoveredPoint ? (
        <div className="mb-3 inline-flex flex-wrap items-center gap-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7] px-3.5 py-2 text-[0.68rem]">
          <span className="font-semibold text-charcoal">{hoveredPoint.label}</span>
          <span className="text-charcoal/70">
            Collected <strong className="font-mono text-charcoal">{formatPaise(hoveredPoint.collectedPaise)}</strong>
          </span>
          <span className="text-charcoal/60">
            {hoveredPoint.receipts} receipt{hoveredPoint.receipts === 1 ? "" : "s"}
          </span>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          width={width}
          height={CHART_HEIGHT}
          role="img"
          aria-label={`Live collections per month for the last ${series.length} months`}
          onMouseLeave={() => setHovered(null)}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PADDING_LEFT}
                y1={yFor(tick)}
                x2={width - PADDING_RIGHT}
                y2={yFor(tick)}
                stroke="#202923"
                strokeOpacity={tick === 0 ? 0.18 : 0.07}
                strokeDasharray={tick === 0 ? undefined : "3 4"}
              />
              <text
                x={PADDING_LEFT - 6}
                y={yFor(tick) + 3}
                textAnchor="end"
                fontSize="9"
                fill="#202923"
                fillOpacity="0.45"
              >
                {formatPaise(tick)}
              </text>
            </g>
          ))}

          {series.map((point, index) => {
            const x = PADDING_LEFT + index * slot + slot / 2;
            const isHovered = hovered === index;
            const height = Math.max(point.collectedPaise > 0 ? 2 : 0, baseY - yFor(point.collectedPaise));
            return (
              <g
                key={point.month}
                onMouseEnter={() => setHovered(index)}
                onTouchStart={() => setHovered(index)}
              >
                <rect
                  x={PADDING_LEFT + index * slot}
                  y={PADDING_TOP}
                  width={slot}
                  height={innerHeight}
                  fill="transparent"
                  className="cursor-crosshair"
                />
                <rect
                  x={x - barWidth / 2}
                  y={yFor(point.collectedPaise)}
                  width={barWidth}
                  height={height}
                  rx={4}
                  fill="#2F5240"
                  fillOpacity={isHovered ? 1 : 0.9}
                />
                <text
                  x={x}
                  y={baseY + 14}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#202923"
                  fillOpacity="0.5"
                >
                  {point.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-2 flex items-center gap-4 text-[0.65rem] text-charcoal/55">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-[#2F5240]" /> Collected (live receipts)
        </span>
      </div>

      <details className="mt-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7]">
        <summary className="cursor-pointer px-4 py-2 text-xs font-semibold text-charcoal/70">
          View as table
        </summary>
        <div className="overflow-x-auto px-4 pb-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-charcoal/50">
                <th scope="col" className="py-1.5 pr-3 font-semibold">Month</th>
                <th scope="col" className="py-1.5 pr-3 font-semibold">Collected</th>
                <th scope="col" className="py-1.5 font-semibold">Receipts</th>
              </tr>
            </thead>
            <tbody>
              {series.map((point) => (
                <tr key={point.month} className="border-t border-charcoal/5 text-charcoal/75">
                  <td className="py-1.5 pr-3 font-medium text-charcoal">{point.label}</td>
                  <td className="py-1.5 pr-3 font-mono">{formatPaise(point.collectedPaise)}</td>
                  <td className="py-1.5 font-mono">{point.receipts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
