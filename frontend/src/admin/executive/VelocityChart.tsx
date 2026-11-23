import { useMemo, useState } from "react";
import type { VelocitySeriesPoint } from "./executiveModel";
import { axisTicks, formatPaise } from "./executiveModel";

interface VelocityChartProps {
  series: VelocitySeriesPoint[];
}

const CHART_HEIGHT = 240;
const PADDING_LEFT = 42;
const PADDING_RIGHT = 12;
const PADDING_TOP = 14;
const PADDING_BOTTOM = 30;

/**
 * Monthly enquiries → visits → bookings grouped bar chart.
 * Mirrors the operator TenantUsageChart pattern (bespoke SVG, hover crosshair,
 * numeric readout, brand forest/sand/charcoal, full legend + table view).
 * Counts and booking value are reported separately — never dual-axis.
 */
export function VelocityChart({ series }: VelocityChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  const { max, ticks } = useMemo(() => {
    const rawMax = series.reduce(
      (acc, p) => Math.max(acc, p.enquiries, p.visits, p.bookings),
      0,
    );
    return axisTicks(rawMax);
  }, [series]);

  const totalActivity = series.reduce(
    (acc, p) => acc + p.enquiries + p.visits + p.bookings,
    0,
  );

  if (series.length === 0 || totalActivity === 0) {
    return (
      <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-charcoal/20 bg-[#FAFAF7] p-6 text-center">
        <p className="text-sm font-semibold text-charcoal">No sales activity in this window</p>
        <p className="mt-1 text-xs text-charcoal/55">
          Enquiries, completed visits and bookings appear here as they happen.
        </p>
      </div>
    );
  }

  const width = Math.max(640, series.length * 64);
  const innerWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const innerHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const baseY = PADDING_TOP + innerHeight;
  const slot = innerWidth / series.length;
  const groupWidth = slot * 0.62;
  const barWidth = Math.max(6, Math.min(14, groupWidth / 3));
  const yFor = (value: number) => baseY - (value / max) * innerHeight;
  const hoveredPoint = hovered !== null ? series[hovered] : null;

  const bars: Array<{ key: "enquiries" | "visits" | "bookings"; label: string; fill: string }> = [
    { key: "enquiries", label: "Enquiries", fill: "#2F5240" },
    { key: "visits", label: "Visits completed", fill: "#C5A77D" },
    { key: "bookings", label: "Bookings", fill: "#9A4A3A" },
  ];

  return (
    <div>
      {hoveredPoint ? (
        <div className="mb-3 inline-flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-charcoal/10 bg-[#FAFAF7] px-3.5 py-2 text-[0.68rem]">
          <span className="font-semibold text-charcoal">{hoveredPoint.label}</span>
          <span className="inline-flex items-center gap-1.5 text-charcoal/70">
            <span aria-hidden="true" className="size-2 rounded-sm bg-[#2F5240]" />
            Enquiries <strong className="font-mono">{hoveredPoint.enquiries}</strong>
          </span>
          <span className="inline-flex items-center gap-1.5 text-charcoal/70">
            <span aria-hidden="true" className="size-2 rounded-sm bg-[#C5A77D]" />
            Visits <strong className="font-mono">{hoveredPoint.visits}</strong>
          </span>
          <span className="inline-flex items-center gap-1.5 text-charcoal/70">
            <span aria-hidden="true" className="size-2 rounded-sm bg-[#9A4A3A]" />
            Bookings <strong className="font-mono">{hoveredPoint.bookings}</strong>
          </span>
          <span className="text-charcoal/60">
            Value <strong className="font-mono text-charcoal">{formatPaise(hoveredPoint.valuePaise)}</strong>
          </span>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          width={width}
          height={CHART_HEIGHT}
          role="img"
          aria-label={`Enquiries, completed visits and bookings per month for the last ${series.length} months`}
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
                fontFamily="monospace"
              >
                {tick}
              </text>
            </g>
          ))}

          {series.map((point, index) => {
            const groupCenter = PADDING_LEFT + index * slot + slot / 2;
            const isHovered = hovered === index;
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
                  fill={isHovered ? "#202923" : "transparent"}
                  fillOpacity={isHovered ? 0.03 : 0}
                  className="cursor-crosshair"
                />
                {bars.map((bar, barIndex) => {
                  const value = point[bar.key];
                  const x = groupCenter - groupWidth / 2 + barIndex * (barWidth + 2);
                  const height = Math.max(value > 0 ? 2 : 0, baseY - yFor(value));
                  return (
                    <rect
                      key={bar.key}
                      x={x}
                      y={yFor(value)}
                      width={barWidth}
                      height={height}
                      rx={3}
                      fill={bar.fill}
                      fillOpacity={isHovered ? 1 : 0.88}
                    />
                  );
                })}
                <text
                  x={groupCenter}
                  y={baseY + 15}
                  textAnchor="middle"
                  fontSize="9.5"
                  fill="#202923"
                  fillOpacity="0.55"
                >
                  {point.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-4 text-[0.65rem] text-charcoal/55">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-[#2F5240]" /> Enquiries
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-[#C5A77D]" /> Visits completed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-[#9A4A3A]" /> Bookings
        </span>
      </div>

      {/* Accessible table view so the chart is never color-alone. */}
      <details className="mt-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7]">
        <summary className="cursor-pointer px-4 py-2 text-xs font-semibold text-charcoal/70">
          View as table
        </summary>
        <div className="overflow-x-auto px-4 pb-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-charcoal/50">
                <th scope="col" className="py-1.5 pr-3 font-semibold">Month</th>
                <th scope="col" className="py-1.5 pr-3 font-semibold">Enquiries</th>
                <th scope="col" className="py-1.5 pr-3 font-semibold">Visits</th>
                <th scope="col" className="py-1.5 pr-3 font-semibold">Bookings</th>
                <th scope="col" className="py-1.5 font-semibold">Booking value</th>
              </tr>
            </thead>
            <tbody>
              {series.map((point) => (
                <tr key={point.month} className="border-t border-charcoal/5 text-charcoal/75">
                  <td className="py-1.5 pr-3 font-medium text-charcoal">{point.label}</td>
                  <td className="py-1.5 pr-3 font-mono">{point.enquiries}</td>
                  <td className="py-1.5 pr-3 font-mono">{point.visits}</td>
                  <td className="py-1.5 pr-3 font-mono">{point.bookings}</td>
                  <td className="py-1.5 font-mono">{formatPaise(point.valuePaise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
