import type { ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { inventoryCardClasses } from "../inventory/inventoryUi";
import type { RiskLevel } from "./intelligenceModel";

const RISK_TONES: Record<RiskLevel, string> = {
  HIGH: "border-rose-200 bg-rose-50 text-rose-700",
  MEDIUM: "border-amber-200 bg-amber-50 text-amber-800",
  LOW: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

export function RiskChip({ risk, label }: { risk: RiskLevel; label?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${RISK_TONES[risk]}`}
    >
      {label ?? risk}
    </span>
  );
}

export function SectionCard({
  title,
  subtitle,
  icon,
  children,
  actions,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className={`${inventoryCardClasses} p-4 sm:p-5`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
            {icon}
            {title}
          </h2>
          {subtitle && <p className="mt-1 text-xs text-charcoal/55">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-24 items-center justify-center gap-2 text-sm text-charcoal/55">
      <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <p className="rounded-lg bg-charcoal/[0.03] px-4 py-6 text-center text-xs text-charcoal/55">
      {label}
    </p>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
    >
      {message}
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-2 font-semibold underline">
          Retry
        </button>
      )}
    </div>
  );
}
