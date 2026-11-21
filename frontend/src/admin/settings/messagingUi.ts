export const CHANNELS = [
  { value: "WHATSAPP", label: "WhatsApp" },
  { value: "SMS", label: "SMS" },
  { value: "EMAIL", label: "Email" },
] as const;

export const DELIVERY_STATUSES = [
  "QUEUED",
  "SENDING",
  "SENT",
  "FAILED",
  "CANCELLED",
] as const;

export const KNOWN_MESSAGING_EVENTS = [
  "lead.created",
  "lead.status_changed",
  "site_visit.booked",
  "site_visit.cancelled",
  "site_visit.reminder_24h",
  "site_visit.reminder_2h",
] as const;

export function channelLabel(channel: string): string {
  return CHANNELS.find((item) => item.value === channel)?.label ?? channel;
}

export function channelBadgeClasses(channel: string): string {
  if (channel === "WHATSAPP") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (channel === "SMS") return "border-blue-200 bg-blue-50 text-blue-800";
  return "border-sand/60 bg-sand/15 text-charcoal/80";
}

export function deliveryStatusClasses(status: string): string {
  if (status === "SENT") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "FAILED" || status === "CANCELLED") {
    return "border-clay/25 bg-clay-soft text-clay";
  }
  if (status === "SENDING") return "border-blue-200 bg-blue-50 text-blue-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export const messagingInputClasses =
  "mt-1.5 block w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-xs text-charcoal placeholder:text-charcoal/40 transition-colors focus:border-forest focus:ring-4 focus:ring-forest/10 focus:outline-hidden disabled:cursor-not-allowed disabled:bg-charcoal/5";

export const messagingLabelClasses =
  "block text-[11px] font-semibold text-charcoal/75";

export const messagingPrimaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-[11px] font-semibold text-white shadow-xs transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-55";

export const messagingSecondaryButton =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-[11px] font-semibold text-charcoal/75 transition-colors hover:bg-charcoal/5 hover:text-charcoal disabled:cursor-not-allowed disabled:opacity-50";

export function formatDeliveryDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
