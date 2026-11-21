import { useEffect, useState } from "react";
import { AlertCircle, Building2, Save } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../auth/api";
import { fetchTenantBranding } from "../../tenant/api";
import { useTenant } from "../../tenant/TenantProvider";
import type { UpdateTenantBrandingPayload } from "../../tenant/types";

interface BrandingSettingsTabProps {
  onUpdate: (payload: UpdateTenantBrandingPayload) => Promise<void>;
  isSaving: boolean;
}

const INPUT_CLASS =
  "mt-1.5 w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-sm text-charcoal outline-none transition-colors focus:border-forest focus:ring-2 focus:ring-forest/15 disabled:bg-charcoal/5";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return "The tenant settings API is not available yet. You can prepare the form, but saving requires GET and ADMIN PUT /api/v1/tenancy/settings.";
  }
  return error instanceof Error ? error.message : "Failed to load branding settings.";
}

export function BrandingSettingsTab({ onUpdate, isSaving }: BrandingSettingsTabProps) {
  const { branding } = useTenant();
  const settingsQuery = useQuery({
    queryKey: ["tenant", "settings", branding.slug],
    queryFn: ({ signal }) => fetchTenantBranding(signal),
    placeholderData: branding,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const current = settingsQuery.data ?? branding;
  const [form, setForm] = useState<UpdateTenantBrandingPayload>({
    brand_name: current.brand_name,
    logo_url: current.logo_url,
    primary_color: current.primary_color,
    theme: current.theme,
    default_dark_mode: current.default_dark_mode,
    currency: current.currency,
    timezone: current.timezone,
    date_format: current.date_format,
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    setForm({
      brand_name: current.brand_name,
      logo_url: current.logo_url,
      primary_color: current.primary_color,
      theme: current.theme,
      default_dark_mode: current.default_dark_mode,
      currency: current.currency,
      timezone: current.timezone,
      date_format: current.date_format,
    });
  }, [current]);

  const setField = <K extends keyof UpdateTenantBrandingPayload>(
    key: K,
    value: UpdateTenantBrandingPayload[K],
  ) => setForm((previous) => ({ ...previous, [key]: value }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setValidationError(null);
    if (!form.brand_name.trim()) {
      setValidationError("Enter a brand name.");
      return;
    }
    try {
      new Intl.DateTimeFormat("en", { timeZone: form.timezone });
    } catch {
      setValidationError("Enter a valid IANA timezone, such as Asia/Kolkata.");
      return;
    }
    await onUpdate({ ...form, brand_name: form.brand_name.trim() });
  };

  return (
    <form onSubmit={handleSubmit} className={`flex flex-col gap-6 ${form.default_dark_mode ? "tenant-dark-form" : ""}`}>
      {settingsQuery.error && (
        <div role="status" className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
          <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{errorMessage(settingsQuery.error)}</span>
        </div>
      )}

      <section className="rounded-2xl border border-charcoal/10 bg-white/80 p-5 shadow-xs">
        <div className="flex items-center gap-2 border-b border-charcoal/10 pb-3">
          <Building2 aria-hidden="true" className="size-4" />
          <h2 className="text-base font-bold tracking-tight">Tenant identity</h2>
        </div>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <label className="text-xs font-semibold text-charcoal/70">
            Brand name
            <input
              value={form.brand_name}
              onChange={(event) => setField("brand_name", event.target.value)}
              maxLength={100}
              required
              className={INPUT_CLASS}
            />
          </label>
          <label className="text-xs font-semibold text-charcoal/70">
            Primary color
            <span className="mt-1.5 flex gap-2">
              <input
                aria-label="Primary color picker"
                type="color"
                value={form.primary_color}
                onChange={(event) => setField("primary_color", event.target.value)}
                className="h-[42px] w-14 cursor-pointer rounded-lg border border-charcoal/15 bg-white p-1"
              />
              <input
                aria-label="Primary color hex code"
                value={form.primary_color}
                onChange={(event) => setField("primary_color", event.target.value)}
                pattern="#[0-9A-Fa-f]{6}"
                required
                className={INPUT_CLASS + " mt-0 font-mono uppercase"}
              />
            </span>
          </label>
          <label className="text-xs font-semibold text-charcoal/70 sm:col-span-2">
            Logo URL
            <input
              type="text"
              inputMode="url"
              value={form.logo_url ?? ""}
              onChange={(event) => setField("logo_url", event.target.value || null)}
              placeholder="https://cdn.example.com/brand-logo.svg"
              maxLength={2048}
              className={INPUT_CLASS}
            />
            <span className="mt-1.5 block font-normal text-charcoal/60">
              HTTPS URLs and API-provided relative paths are supported. Leave blank for the text mark.
            </span>
          </label>
          <label className="text-xs font-semibold text-charcoal/70 sm:col-span-2">
            Logo file upload
            <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" disabled className={INPUT_CLASS} />
            <span className="mt-1.5 block font-normal text-charcoal/60">
              File upload is unavailable until the backend defines its multipart or logo-upload contract and validation limits.
            </span>
          </label>
        </div>
      </section>

      <section className="rounded-2xl border border-charcoal/10 bg-white/80 p-5 shadow-xs">
        <h2 className="border-b border-charcoal/10 pb-3 text-base font-bold tracking-tight">Regional preferences</h2>
        <div className="mt-5 grid gap-5 sm:grid-cols-3">
          <label className="text-xs font-semibold text-charcoal/70">
            Currency (ISO code)
            <input
              value={form.currency}
              onChange={(event) => setField("currency", event.target.value.toUpperCase())}
              pattern="[A-Z]{3}"
              maxLength={3}
              required
              className={INPUT_CLASS}
            />
          </label>
          <label className="text-xs font-semibold text-charcoal/70">
            IANA timezone
            <input
              value={form.timezone}
              onChange={(event) => setField("timezone", event.target.value)}
              placeholder="Asia/Kolkata"
              required
              className={INPUT_CLASS}
            />
          </label>
          <label className="text-xs font-semibold text-charcoal/70">
            Date format
            <input
              value={form.date_format}
              onChange={(event) => setField("date_format", event.target.value)}
              placeholder="dd MMM yyyy"
              required
              className={INPUT_CLASS}
            />
          </label>
          <label className="flex cursor-pointer items-center gap-3 text-xs font-semibold text-charcoal/70 sm:col-span-3">
            <input
              type="checkbox"
              checked={form.default_dark_mode}
              onChange={(event) => {
                const enabled = event.target.checked;
                setForm((previous) => ({
                  ...previous,
                  default_dark_mode: enabled,
                  theme: enabled ? "dark" : "light",
                }));
              }}
              className="size-4 rounded border-charcoal/20"
            />
            Use dark mode by default for new visitors
          </label>
        </div>
        <p className="mt-4 text-xs leading-5 text-charcoal/60">
          Theme and regional values are exposed through the tenant context. Existing light screens retain their current visual design; full dark layouts and tenant-wide date/currency formatting are follow-up integration work.
        </p>
      </section>

      {validationError && <p role="alert" className="text-sm text-red-700">{validationError}</p>}
      <div className="flex justify-end">
        <button type="submit" disabled={isSaving} className="inline-flex items-center gap-2 rounded-xl brand-button px-5 py-2.5 text-xs font-semibold shadow-xs disabled:opacity-50">
          <Save aria-hidden="true" className="size-4" />
          {isSaving ? "Saving branding..." : "Save branding settings"}
        </button>
      </div>
    </form>
  );
}
