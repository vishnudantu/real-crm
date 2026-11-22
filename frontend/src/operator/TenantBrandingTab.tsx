import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Code2, LoaderCircle, Save } from "lucide-react";
import { patchTenantConfig } from "./api";
import { errorMessage } from "../shared/apiRequest";
import { themeString } from "./operatorModel";
import type { TenantConfig } from "./operatorModel";
import { InlineNotice, LoadingBlock, CopyButton, inputClasses, labelClasses, primaryButtonClasses } from "./ui";

interface TenantBrandingTabProps {
  tenantId: string;
  config: TenantConfig | undefined;
  loading: boolean;
  canWrite: boolean;
}

interface BrandingFormState {
  brand_name: string;
  country: string;
  timezone: string;
  currency: string;
  primaryColor: string;
  welcomeMessage: string;
}

function formFromConfig(config: TenantConfig | undefined): BrandingFormState {
  const theme = config?.branding.theme_json ?? {};
  return {
    brand_name: config?.branding.brand_name ?? "",
    country: config?.country ?? "IN",
    timezone: config?.timezone ?? "Asia/Kolkata",
    currency: config?.currency ?? "INR",
    primaryColor: themeString(theme, "primary").toUpperCase() || "#536B59",
    welcomeMessage: themeString(theme, "welcome_message"),
  };
}

const HEX_PATTERN = /^#[0-9A-Fa-f]{6}$/;

export function TenantBrandingTab({
  tenantId,
  config,
  loading,
  canWrite,
}: TenantBrandingTabProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BrandingFormState>(() => formFromConfig(config));
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    setForm(formFromConfig(config));
    setNotice(null);
  }, [config]);

  const baseline = useMemo(() => formFromConfig(config), [config]);
  const dirtyBrand = form.brand_name.trim() !== baseline.brand_name.trim();
  const dirtyCountry = form.country.trim().toUpperCase() !== baseline.country.trim().toUpperCase();
  const dirtyTimezone = form.timezone.trim() !== baseline.timezone.trim();
  const dirtyCurrency = form.currency.trim().toUpperCase() !== baseline.currency.trim().toUpperCase();
  const dirtyColor = form.primaryColor.toUpperCase() !== baseline.primaryColor.toUpperCase();
  const dirtyWelcome = form.welcomeMessage !== baseline.welcomeMessage;
  const isDirty = dirtyBrand || dirtyCountry || dirtyTimezone || dirtyCurrency || dirtyColor || dirtyWelcome;

  const setField = <K extends keyof BrandingFormState>(key: K, value: BrandingFormState[K]) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  const mutation = useMutation({
    mutationFn: () => {
      const payload: {
        brand_name?: string;
        country?: string;
        timezone?: string;
        currency?: string;
        theme_json?: Record<string, unknown>;
      } = {};
      if (dirtyBrand) payload.brand_name = form.brand_name.trim();
      if (dirtyCountry) payload.country = form.country.trim().toUpperCase();
      if (dirtyTimezone) payload.timezone = form.timezone.trim();
      if (dirtyCurrency) payload.currency = form.currency.trim().toUpperCase();
      const themeJson: Record<string, unknown> = {};
      if (dirtyColor) themeJson.primary = form.primaryColor.toUpperCase();
      if (dirtyWelcome) themeJson.welcome_message = form.welcomeMessage;
      if (Object.keys(themeJson).length > 0) payload.theme_json = themeJson;
      return patchTenantConfig(tenantId, payload);
    },
    onSuccess: async () => {
      setNotice({ tone: "success", text: "Branding and locale saved. Unknown theme keys are preserved." });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "config"] }),
        queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId] }),
        queryClient.invalidateQueries({ queryKey: ["operator", "tenants", tenantId, "health"] }),
      ]);
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: errorMessage(error, "Failed to save tenant configuration.") });
    },
  });

  if (loading || !config) {
    return <LoadingBlock label="Loading tenant branding…" />;
  }

  const invalidColor = !HEX_PATTERN.test(form.primaryColor);
  const embedUrl = config.widget.embed_url;

  return (
    <div className="space-y-5">
      {notice ? <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice> : null}

      <div className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <h3 className="text-sm font-semibold text-charcoal">Identity &amp; locale</h3>
        <p className="mt-1 text-xs text-charcoal/55">
          Sent as PATCH /operator/tenants/{'{tenant}'}/config — only changed fields are submitted; unknown
          theme keys stay untouched.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="brand-name" className={labelClasses}>Brand name</label>
            <input
              id="brand-name"
              value={form.brand_name}
              maxLength={255}
              disabled={!canWrite}
              onChange={(event) => setField("brand_name", event.target.value)}
              className={inputClasses}
            />
          </div>
          <div>
            <label htmlFor="brand-country" className={labelClasses}>Country (ISO-3166)</label>
            <input
              id="brand-country"
              value={form.country}
              maxLength={2}
              disabled={!canWrite}
              onChange={(event) => setField("country", event.target.value.toUpperCase())}
              className={`${inputClasses} uppercase`}
            />
          </div>
          <div>
            <label htmlFor="brand-currency" className={labelClasses}>Currency (ISO-4217)</label>
            <input
              id="brand-currency"
              value={form.currency}
              maxLength={3}
              disabled={!canWrite}
              onChange={(event) => setField("currency", event.target.value.toUpperCase())}
              className={`${inputClasses} uppercase`}
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="brand-timezone" className={labelClasses}>Timezone (IANA)</label>
            <input
              id="brand-timezone"
              value={form.timezone}
              placeholder="Asia/Kolkata"
              disabled={!canWrite}
              onChange={(event) => setField("timezone", event.target.value)}
              className={inputClasses}
            />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <h3 className="text-sm font-semibold text-charcoal">Widget theme &amp; greeting</h3>
        <p className="mt-1 text-xs text-charcoal/55">
          Stored in the tenant theme blob (primary color, welcome message).
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <span className={labelClasses}>Primary color</span>
            <div className="mt-1.5 flex gap-2">
              <input
                type="color"
                aria-label="Theme primary color picker"
                value={HEX_PATTERN.test(form.primaryColor) ? form.primaryColor : "#536B59"}
                disabled={!canWrite}
                onChange={(event) => setField("primaryColor", event.target.value.toUpperCase())}
                className="h-[42px] w-14 shrink-0 cursor-pointer rounded-lg border border-charcoal/15 bg-white p-1 disabled:cursor-not-allowed"
              />
              <input
                aria-label="Theme primary color hex"
                value={form.primaryColor}
                maxLength={7}
                disabled={!canWrite}
                onChange={(event) => setField("primaryColor", event.target.value)}
                className={`${inputClasses} mt-0 ${invalidColor ? "border-clay" : ""}`}
              />
            </div>
            {invalidColor ? (
              <p className="mt-1.5 text-xs text-clay">Use a #RRGGBB hex value.</p>
            ) : null}
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="brand-welcome" className={labelClasses}>Widget welcome message</label>
            <textarea
              id="brand-welcome"
              rows={2}
              maxLength={300}
              disabled={!canWrite}
              placeholder="Hi! Have a question about our projects?"
              value={form.welcomeMessage}
              onChange={(event) => setField("welcomeMessage", event.target.value)}
              className={`${inputClasses} resize-y`}
            />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <div className="flex items-center gap-2">
          <Code2 aria-hidden="true" className="size-4 text-charcoal/50" />
          <h3 className="text-sm font-semibold text-charcoal">Widget embed</h3>
        </div>
        {embedUrl ? (
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <code className="min-w-0 flex-1 truncate rounded-xl border border-charcoal/10 bg-charcoal/[0.04] px-3.5 py-2.5 font-mono text-xs text-charcoal">
              {`<script src="${window.location.origin}${embedUrl}" async></script>`}
            </code>
            <CopyButton value={`<script src="${window.location.origin}${embedUrl}" async></script>`} label="Copy embed" />
          </div>
        ) : (
          <p className="mt-3 text-xs leading-5 text-charcoal/55">
            The web_widget feature is disabled for this tenant, so no embed URL
            is served. Enable it under Entitlements to get the script tag.
          </p>
        )}
      </div>

      {canWrite ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[0.68rem] text-charcoal/50">
            {isDirty ? "Unsaved changes on this tab." : "Everything is in sync with the server."}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!isDirty || mutation.isPending}
              onClick={() => {
                setNotice(null);
                setForm(formFromConfig(config));
              }}
              className="inline-flex min-h-10 items-center rounded-xl border border-charcoal/15 bg-white px-4 text-xs font-semibold text-charcoal/70 disabled:opacity-50"
            >
              Revert
            </button>
            <button
              type="button"
              disabled={!isDirty || invalidColor || mutation.isPending}
              onClick={() => mutation.mutate()}
              className={primaryButtonClasses}
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Save aria-hidden="true" className="size-4" />
              )}
              Save configuration
            </button>
          </div>
        </div>
      ) : (
        <p className="flex items-center gap-2 text-xs text-charcoal/55">
          <Check aria-hidden="true" className="size-3.5 text-forest" />
          You have read-only access to tenant configuration.
        </p>
      )}
    </div>
  );
}
