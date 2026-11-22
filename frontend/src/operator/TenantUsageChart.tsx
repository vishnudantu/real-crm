import { useMemo, useState } from "react";
import type { TenantUsageDailyPoint } from "./operatorModel";
import { formatIsoDay } from "./operatorModel";

interface TenantUsageChartProps {
  series: TenantUsageDailyPoint[];
}

const CHART_HEIGHT = 220;
const PADDING_LEFT = 40;
const PADDING_RIGHT = 12;
const PADDING_TOP = 14;
const PADDING_BOTTOM = 30;

function niceMax(rawMax: number): { max: number; step: number } {
  if (rawMax <= 4) return { max: Math.max(4, rawMax), step: 1 };
  const magnitude = 10 ** Math.floor(Math.log10(rawMax));
  const normalized = rawMax / magnitude;
  const step =
    normalized <= 1 ? magnitude / 4 : normalized <= 2 ? magnitude / 2 : normalized <= 5 ? magnitude : magnitude * 2;
  const max = Math.ceil(rawMax / step) * step;
  return { max, step };
}

/**
 * Bespoke dual-series daily bar chart (leads vs messages sent).
 * Simplified from the admin LeadTrendsChart pattern; bars instead of splines.
 */
export function TenantUsageChart({ series }: TenantUsageChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  const { max, ticks } = useMemo(() => {
    const rawMax = series.reduce(
      (acc, point) => Math.max(acc, point.leads, point.messages_sent),
      0,
    );
    const nice = niceMax(rawMax);
    const values: number[] = [];
    for (let value = 0; value <= nice.max; value += nice.step) values.push(value);
    return { max: nice.max, ticks: values };
  }, [series]);

  if (series.length === 0) {
    return (
      <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-charcoal/20 bg-[#FAFAF7] p-6 text-center">
        <p className="text-sm font-semibold text-charcoal">No daily activity in this window</p>
        <p className="mt-1 text-xs text-charcoal/55">
          Leads and outbound messages appear here as buyers interact.
        </p>
      </div>
    );
  }

  const width = Math.max(560, series.length * 26);
  const innerWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const innerHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const baseY = PADDING_TOP + innerHeight;
  const slot = innerWidth / series.length;
  const barWidth = Math.max(4, Math.min(9, slot / 2.6));
  const yFor = (value: number) => baseY - (value / max) * innerHeight;
  const labelEvery = series.length > 30 ? 7 : series.length > 14 ? 5 : 3;
  const hoveredPoint = hovered !== null ? series[hovered] : null;

  return (
    <div>
      {hoveredPoint ? (
        <div className="mb-3 inline-flex flex-wrap items-center gap-3 rounded-xl border border-charcoal/10 bg-[#FAFAF7] px-3.5 py-2 text-[0.68rem]">
          <span className="font-semibold text-charcoal">{formatIsoDay(hoveredPoint.date)}</span>
          <span className="inline-flex items-center gap-1.5 text-charcoal/70">
            <span aria-hidden="true" className="size-2 rounded-sm bg-forest" />
            Leads <strong className="font-mono">{hoveredPoint.leads}</strong>
          </span>
          <span className="inline-flex items-center gap-1.5 text-charcoal/70">
            <span aria-hidden="true" className="size-2 rounded-sm bg-sand" />
            Messages <strong className="font-mono">{hoveredPoint.messages_sent}</strong>
          </span>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          width={width}
          height={CHART_HEIGHT}
          role="img"
          aria-label={`Daily leads and messages for the last ${series.length} days`}
          onMouseLeave={() => setHovered(null)}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PADDING_LEFT}
                y1={yFor(tick)}
                x2={width - PADDING_RIGHT}
                y2={yFor(tick)}
                stroke="#1F2421"
                strokeOpacity={tick === 0 ? 0.18 : 0.07}
                strokeDasharray={tick === 0 ? undefined : "3 4"}
              />
              <text
                x={PADDING_LEFT - 6}
                y={yFor(tick) + 3}
                textAnchor="end"
                fontSize="9"
                fill="#1F2421"
                fillOpacity="0.45"
                fontFamily="monospace"
              >
                {tick}
              </text>
            </g>
          ))}

          {series.map((point, index) => {
            const x = PADDING_LEFT + index * slot + slot / 2;
            const isHovered = hovered === index;
            return (
              <g
                key={point.date}
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
                  x={x - barWidth - 1}
                  y={yFor(point.leads)}
                  width={barWidth}
                  height={Math.max(point.leads > 0 ? 2 : 0, baseY - yFor(point.leads))}
                  rx={2}
                  fill="#2F5240"
                  fillOpacity={isHovered ? 1 : 0.88}
                />
                <rect
                  x={x + 1}
                  y={yFor(point.messages_sent)}
                  width={barWidth}
                  height={Math.max(point.messages_sent > 0 ? 2 : 0, baseY - yFor(point.messages_sent))}
                  rx={2}
                  fill="#C5A77D"
                  fillOpacity={isHovered ? 1 : 0.85}
                />
                {index % labelEvery === 0 || index === series.length - 1 ? (
                  <text
                    x={x}
                    y={baseY + 14}
                    textAnchor="middle"
                    fontSize="8.5"
                    fill="#1F2421"
                    fillOpacity="0.5"
                  >
                    {formatIsoDay(point.date)}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-2 flex items-center gap-4 text-[0.65rem] text-charcoal/55">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-forest" /> Leads captured
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm bg-sand" /> Messages sent
        </span>
      </div>
    </div>
  );
}
