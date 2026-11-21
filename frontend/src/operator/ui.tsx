import type { ReactNode } from "react";
import { AlertTriangle, LoaderCircle, RotateCw } from "lucide-react";
import { useModalFocus } from "../shared/useModalFocus";

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
