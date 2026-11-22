import type { LucideIcon } from "lucide-react";
import {
  BadgeCheck,
  Ban,
  BookCheck,
  CircleAlert,
  CircleCheck,
  File,
  FileCheck,
  Gavel,
  Hourglass,
  Lock,
  ShieldCheck,
} from "lucide-react";
import type { StatusIconName, StatusTone } from "./inventoryModel";
import { statusLabel, statusVisual } from "./inventoryModel";

export const inventoryInputClasses =
  "mt-1.5 block w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-xs text-charcoal placeholder:text-charcoal/40 transition-colors focus:border-forest focus:ring-4 focus:ring-forest/10 focus:outline-hidden disabled:cursor-not-allowed disabled:bg-charcoal/5";

export const inventoryLabelClasses = "block text-[11px] font-semibold text-charcoal/75";

export const inventoryPrimaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-[11px] font-semibold text-white shadow-xs transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-55";

export const inventorySecondaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-[11px] font-semibold text-charcoal/75 transition-colors hover:bg-charcoal/5 hover:text-charcoal disabled:cursor-not-allowed disabled:opacity-50";

export const inventoryDangerButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl border border-rose-300 bg-white px-3.5 py-2 text-[11px] font-semibold text-rose-700 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50";

export const inventoryCardClasses = "rounded-2xl border border-charcoal/10 bg-white shadow-xs";

const STATUS_ICONS: Readonly<Record<StatusIconName, LucideIcon>> = {
  "circle-check": CircleCheck,
  hourglass: Hourglass,
  "shield-check": ShieldCheck,
  "book-check": BookCheck,
  "badge-check": BadgeCheck,
  lock: Lock,
  gavel: Gavel,
  file: File,
  "file-check": FileCheck,
  ban: Ban,
  "circle-alert": CircleAlert,
};

export function StatusIcon({
  status,
  className = "size-3.5",
}: {
  status: string;
  className?: string;
}) {
  const Icon = STATUS_ICONS[statusVisual(status).icon];
  return <Icon aria-hidden="true" className={className} />;
}

const BADGE_TONES: Readonly<Record<StatusTone, string>> = {
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  violet: "border-violet-200 bg-violet-50 text-violet-800",
  blue: "border-blue-200 bg-blue-50 text-blue-800",
  sky: "border-sky-200 bg-sky-50 text-sky-800",
  rose: "border-rose-200 bg-rose-50 text-rose-800",
  slate: "border-slate-200 bg-slate-100 text-slate-700",
  stone: "border-stone-200 bg-stone-100 text-stone-600",
};

export function StatusBadge({ status }: { status: string }) {
  const visual = statusVisual(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${BADGE_TONES[visual.tone]}`}
    >
      <StatusIcon status={status} className="size-3" />
      {statusLabel(status)}
    </span>
  );
}

/** Cell colours for the map: every tone also carries an icon + status text. */
export const CELL_TONES: Readonly<Record<StatusTone, string>> = {
  emerald: "border-emerald-300 bg-emerald-50 text-emerald-900 hover:border-emerald-500",
  amber: "border-amber-300 bg-amber-50 text-amber-900 hover:border-amber-500",
  violet: "border-violet-300 bg-violet-50 text-violet-900 hover:border-violet-500",
  blue: "border-blue-300 bg-blue-50 text-blue-900 hover:border-blue-500",
  sky: "border-sky-300 bg-sky-50 text-sky-900 hover:border-sky-500",
  rose: "border-rose-300 bg-rose-50 text-rose-900 hover:border-rose-500",
  slate: "border-slate-300 bg-slate-50 text-slate-800 hover:border-slate-500",
  stone: "border-stone-300 bg-stone-50 text-stone-700 hover:border-stone-400",
};

export const LEGEND_DOT_TONES: Readonly<Record<StatusTone, string>> = {
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  violet: "bg-violet-400",
  blue: "bg-blue-400",
  sky: "bg-sky-400",
  rose: "bg-rose-400",
  slate: "bg-slate-400",
  stone: "bg-stone-400",
};

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}
