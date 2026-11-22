import { useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  LoaderCircle,
  RotateCw,
} from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";
import type { HealthState } from "./operatorModel";

export const inputClasses =
  "mt-1.5 block w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal placeholder:text-charcoal/40 transition-colors focus:border-forest focus:ring-4 focus:ring-forest/10 focus:outline-hidden disabled:cursor-not-allowed disabled:bg-charcoal/5";

export const labelClasses = "block text-xs font-semibold text-charcoal/75";

export const primaryButtonClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-forest px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-55";

export const secondaryButtonClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal/80 transition-colors hover:border-charcoal/30 hover:bg-charcoal/5 hover:text-charcoal disabled:cursor-not-allowed disabled:opacity-50";

interface SectionHeaderProps {
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: SectionHeaderProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-charcoal/10 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div className="min-w-0">
        <p className="text-[0.62rem] font-semibold tracking-[0.18em] text-forest uppercase">
          {eyebrow}
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-charcoal">
          {title}
        </h2>
        {description ? (
          <p className="mt-1 max-w-2xl text-xs leading-5 text-charcoal/60">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

interface SurfaceProps {
  children: ReactNode;
  className?: string;
}

export function Surface({ children, className = "" }: SurfaceProps) {
  return (
    <section
      className={`rounded-2xl border border-charcoal/10 bg-white shadow-xs ${className}`}
    >
      {children}
    </section>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "active" ||
    status === "SENT" ||
    status === "QUEUED" ||
    status === "SENDING"
      ? "border-forest/25 bg-forest/10 text-forest-deep"
      : "border-clay/25 bg-clay-soft text-clay";
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[0.62rem] font-semibold tracking-wider uppercase ${tone}`}
    >
      {status}
    </span>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex min-h-40 items-center justify-center gap-2 px-5 py-8 text-sm text-charcoal/60"
    >
      <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

interface ErrorBlockProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorBlock({ message, onRetry }: ErrorBlockProps) {
  return (
    <div role="alert" className="p-5 sm:p-6">
      <div className="flex items-start gap-3 rounded-xl border border-clay/25 bg-clay-soft/60 p-4 text-sm text-clay">
        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">This section could not be loaded</p>
          <p className="mt-1 text-xs leading-5">{message}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-charcoal/20 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal"
            >
              <RotateCw aria-hidden="true" className="size-3.5" />
              Try again
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

interface ModalProps {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  widthClass?: string;
}

export function Modal({
  title,
  description,
  onClose,
  children,
  widthClass = "max-w-2xl",
}: ModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`max-h-[90svh] w-full ${widthClass} overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-charcoal">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-xs leading-5 text-charcoal/60">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-lg border border-charcoal/10 px-2.5 py-1.5 text-sm text-charcoal/60 transition-colors hover:bg-charcoal/5 hover:text-charcoal"
          >
            ×
          </button>
        </div>
        <div className="p-5 sm:p-6">{children}</div>
      </div>
    </div>
  );
}

export function InlineNotice({
  tone,
  children,
}: {
  tone: "error" | "success";
  children: ReactNode;
}) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`mb-4 rounded-xl border px-3.5 py-2.5 text-xs leading-5 ${
        tone === "error"
          ? "border-clay/25 bg-clay-soft text-clay"
          : "border-forest/25 bg-forest/10 text-forest-deep"
      }`}
    >
      {children}
    </p>
  );
}

const HEALTH_CHIP_TONES: Record<HealthState, string> = {
  green: "border-forest/25 bg-forest/10 text-forest-deep",
  yellow: "border-amber-400/40 bg-amber-50 text-amber-800",
  red: "border-clay/30 bg-clay-soft text-clay",
};

const HEALTH_DOT_TONES: Record<HealthState, string> = {
  green: "bg-forest",
  yellow: "bg-amber-500",
  red: "bg-clay",
};

export function healthStateOf(state: string): HealthState {
  return state === "red" ? "red" : state === "green" ? "green" : "yellow";
}

interface HealthChipProps {
  state: string;
  label?: string;
  title?: string;
}

export function HealthChip({ state, label, title }: HealthChipProps) {
  const tone = healthStateOf(state);
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.62rem] font-semibold tracking-wider uppercase ${HEALTH_CHIP_TONES[tone]}`}
    >
      <span aria-hidden="true" className={`size-1.5 rounded-full ${HEALTH_DOT_TONES[tone]}`} />
      {label ?? tone}
    </span>
  );
}

interface CopyButtonProps {
  value: string;
  label?: string;
  className?: string;
}

export function CopyButton({ value, label = "Copy", className = "" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard can be blocked; the value remains visible for manual copy.
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <button
      type="button"
      onClick={() => void copy()}
      aria-label={`Copy ${label.toLowerCase()}`}
      className={
        className ||
        "inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-charcoal/15 bg-white px-2.5 text-[0.68rem] font-semibold text-charcoal/70 transition-colors hover:bg-charcoal/5 hover:text-charcoal"
      }
    >
      {copied ? (
        <Check aria-hidden="true" className="size-3.5 text-forest" />
      ) : (
        <Copy aria-hidden="true" className="size-3.5" />
      )}
      {copied ? "Copied" : label}
    </button>
  );
}

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
}

interface TabBarProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  ariaLabel: string;
}

export function TabBar({ tabs, active, onChange, ariaLabel }: TabBarProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex gap-1 overflow-x-auto rounded-2xl border border-charcoal/10 bg-white p-1.5 shadow-xs"
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition-colors ${
              isActive
                ? "bg-charcoal text-ivory shadow-xs"
                : "text-charcoal/60 hover:bg-charcoal/5 hover:text-charcoal"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

interface MeterBarProps {
  percent: number | null;
  tone?: "forest" | "clay" | "amber";
}

export function MeterBar({ percent, tone = "forest" }: MeterBarProps) {
  if (percent === null) {
    return (
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-charcoal/5">
        <div className="h-full w-full bg-charcoal/10" />
      </div>
    );
  }
  const resolvedTone =
    percent >= 95 ? "bg-clay" : percent >= 80 ? "bg-amber-500" : tone === "forest" ? "bg-forest" : "bg-clay";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-charcoal/5">
      <div
        className={`h-full rounded-full ${resolvedTone} transition-all`}
        style={{ width: `${Math.max(2, Math.min(100, percent))}%` }}
      />
    </div>
  );
}
