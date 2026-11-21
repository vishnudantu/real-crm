export const saleInputClasses =
  "mt-1.5 block w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-xs text-charcoal placeholder:text-charcoal/40 transition-colors focus:border-forest focus:ring-4 focus:ring-forest/10 focus:outline-hidden disabled:cursor-not-allowed disabled:bg-charcoal/5";

export const saleLabelClasses = "block text-[11px] font-semibold text-charcoal/75";

export const salePrimaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-[11px] font-semibold text-white shadow-xs transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-55";

export const saleSecondaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-[11px] font-semibold text-charcoal/75 transition-colors hover:bg-charcoal/5 hover:text-charcoal disabled:cursor-not-allowed disabled:opacity-50";

export const saleDangerButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl border border-rose-300 bg-white px-3.5 py-2 text-[11px] font-semibold text-rose-700 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50";

export const saleCardClasses =
  "rounded-2xl border border-charcoal/10 bg-white shadow-xs";

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const inrFormatterShort = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatInr(paise: number): string {
  return inrFormatter.format(paise / 100);
}

export function formatInrCompact(paise: number): string {
  if (paise % 100 === 0) return inrFormatterShort.format(paise / 100);
  return inrFormatter.format(paise / 100);
}

const shortDateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return shortDateFormatter.format(parsed);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return dateTimeFormatter.format(parsed);
}

export function rupeesInputToPaise(value: string): number {
  const trimmed = value.trim().replace(/,/g, "");
  if (!trimmed) return Number.NaN;
  if (!/^\d+(\.\d{0,2})?$/.test(trimmed)) return Number.NaN;
  return Math.round(Number(trimmed) * 100);
}

export function paiseToRupeesInput(paise: number): string {
  const rupees = paise / 100;
  return Number.isInteger(rupees) ? String(rupees) : rupees.toFixed(2);
}
