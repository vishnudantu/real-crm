import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "../shared/apiRequest";

export const customerInputClass = "w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal outline-none transition-colors placeholder:text-charcoal/35 focus:border-charcoal/45 disabled:cursor-not-allowed disabled:bg-charcoal/5";

export function CustomerPageHeader({ eyebrow, title, description, action }: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="text-[0.65rem] font-semibold tracking-[0.18em] text-charcoal/50 uppercase">{eyebrow}</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">{description}</p>
      </div>
      {action}
    </header>
  );
}

export function CustomerSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading customer data" className="space-y-3 animate-pulse">
      <span className="sr-only">Loading customer data…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="h-24 rounded-2xl border border-charcoal/5 bg-charcoal/5" />
      ))}
    </div>
  );
}

export function CustomerErrorBanner({ error, fallback, onRetry }: {
  error: unknown;
  fallback: string;
  onRetry?: () => void;
}) {
  if (!error) return null;
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 sm:flex-row sm:items-center">
      <AlertCircle aria-hidden="true" className="size-5 shrink-0 text-rose-600" />
      <p className="min-w-0 flex-1 leading-6">{errorMessage(error, fallback)}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="inline-flex shrink-0 items-center gap-1.5 self-start text-xs font-semibold underline hover:no-underline sm:self-auto">
          <RefreshCw aria-hidden="true" className="size-3.5" /> Try again
        </button>
      )}
    </div>
  );
}

export function CustomerEmptyState({ title, description, action }: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-charcoal/20 bg-white px-5 py-12 text-center">
      <span className="mx-auto grid size-11 place-items-center rounded-xl bg-charcoal/5 text-charcoal/50"><Inbox aria-hidden="true" className="size-5" /></span>
      <h2 className="mt-4 text-sm font-semibold text-charcoal">{title}</h2>
      <p className="mx-auto mt-1.5 max-w-md text-xs leading-5 text-charcoal/55">{description}</p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function formatCustomerDate(value: string, includeTime = false): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-US", includeTime
    ? { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }
    : { month: "short", day: "numeric", year: "numeric" }).format(date);
}

export function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}
