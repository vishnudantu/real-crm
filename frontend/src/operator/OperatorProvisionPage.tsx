import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CircleAlert,
  LoaderCircle,
  MessageCircle,
  Phone,
  Plug,
  ReceiptText,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import { fetchOperatorPlans, onboardTenant, provisionTenant } from "./api";
import { errorMessage } from "../shared/apiRequest";
import type {
  OnboardTenantResponse,
  ProvisionTenantResponse,
} from "./operatorModel";
import { isUuidLike } from "./operatorModel";
import {
  InlineNotice,
  LoadingBlock,
  CopyButton,
  SectionHeader,
  Surface,
  inputClasses,
  labelClasses,
  primaryButtonClasses,
  secondaryButtonClasses,
} from "./ui";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const identitySchema = z.object({
  slug: z
    .string()
    .trim()
    .min(2, "Enter a tenant slug.")
    .max(100)
    .regex(SLUG_PATTERN, "Use lowercase letters, numbers, and hyphens."),
  name: z.string().trim().min(2, "Enter the legal organization name.").max(255),
  brandName: z.string().trim().max(255),
  country: z.string().trim().length(2, "Use a two-letter country code."),
  timezone: z.string().trim().min(1, "Enter an IANA timezone."),
  currency: z.string().trim().length(3, "Use a three-letter currency code."),
});

const adminSchema = z.object({
  adminFullName: z.string().trim().min(2, "Enter the administrator's full name.").max(255),
  adminEmail: z.string().trim().email("Enter a valid admin email address."),
  adminPassword: z
    .string()
    .min(12, "Use at least 12 characters.")
    .max(128)
    .regex(/[a-z]/, "Include a lowercase letter.")
    .regex(/[A-Z]/, "Include an uppercase letter.")
    .regex(/\d/, "Include a number.")
    .regex(/[^A-Za-z0-9]/, "Include a symbol."),
});

interface IdentityValues extends z.infer<typeof identitySchema> {}
interface AdminValues extends z.infer<typeof adminSchema> {}

interface WizardState {
  identity: IdentityValues;
  admin: AdminValues;
  planCode: string;
  enableOmnichannel: boolean;
  enableCalling: boolean;
  enableConnectors: boolean;
  enablePostSales: boolean;
}

const INITIAL_STATE: WizardState = {
  identity: {
    slug: "",
    name: "",
    brandName: "",
    country: "IN",
    timezone: "Asia/Kolkata",
    currency: "INR",
  },
  admin: { adminFullName: "", adminEmail: "", adminPassword: "" },
  planCode: "",
  enableOmnichannel: false,
  enableCalling: false,
  enableConnectors: false,
  enablePostSales: false,
};

const WIZARD_STEPS = [
  { id: 1, label: "Identity", hint: "Workspace, locale, and admin account" },
  { id: 2, label: "Plan", hint: "Pick a subscription from the catalog" },
  { id: 3, label: "Capabilities", hint: "Opt in to product surfaces" },
  { id: 4, label: "Review", hint: "Confirm and provision" },
] as const;

const FEATURE_OPTINS = [
  {
    key: "enableOmnichannel" as const,
    icon: MessageCircle,
    label: "Omnichannel inbox + WhatsApp",
    hint: "One inbox for WhatsApp and web chat; provisions the channel credential surface and the widget embed.",
  },
  {
    key: "enableCalling" as const,
    icon: Phone,
    label: "Browser calling",
    hint: "In-app WebRTC calls with recording for the tenant sales team.",
  },
  {
    key: "enableConnectors" as const,
    icon: Plug,
    label: "Lead connectors",
    hint: "Meta Lead Ads and portal email ingestion into the tenant pipeline.",
  },
  {
    key: "enablePostSales" as const,
    icon: ReceiptText,
    label: "Post-sales pack",
    hint: "Sale bookings, payment plans, receipts, and commissions.",
  },
];

function fieldErrorsOf(error: z.ZodError): Record<string, string> {
  const map: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    if (!map[key]) map[key] = issue.message;
  }
  return map;
}

export function OperatorProvisionPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"wizard" | "advanced">("wizard");

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        to="/operator"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal/60 transition-colors hover:text-charcoal"
      >
        <ArrowLeft aria-hidden="true" className="size-3.5" />
        Mission Control
      </Link>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Onboarding
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Onboard a tenant
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
            A guided wizard provisions the workspace, its plan, starter
            capabilities, and the first administrator in one audited call.
          </p>
        </div>
        <div className="flex rounded-xl border border-charcoal/10 bg-charcoal/5 p-1">
          {(
            [
              ["wizard", "Wizard"],
              ["advanced", "Advanced form"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                mode === value
                  ? "bg-white text-charcoal shadow-xs"
                  : "text-charcoal/55 hover:text-charcoal"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6">
        {mode === "wizard" ? (
          <OnboardingWizard onCancel={() => navigate("/operator")} />
        ) : (
          <AdvancedProvisionForm />
        )}
      </div>
    </div>
  );
}

function OnboardingWizard({ onCancel }: { onCancel: () => void }) {
  const navigate = useNavigate();
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });
  const [step, setStep] = useState(1);
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<OnboardTenantResponse | null>(null);

  const patch = (changes: Partial<WizardState>) =>
    setState((previous) => ({ ...previous, ...changes }));

  const slugTouched = state.identity.slug.length > 0;
  const slugValid = SLUG_PATTERN.test(state.identity.slug);
  const plans = plansQuery.data ?? [];
  const selectedPlan = plans.find((plan) => plan.code === state.planCode) ?? null;
  const previewEmbedUrl = state.enableOmnichannel
    ? `/api/v1/widget/${state.identity.slug || "{slug}"}/embed.js`
    : null;

  const validateStep = (target: number): boolean => {
    if (target === 1) {
      const identity = identitySchema.safeParse(state.identity);
      const admin = adminSchema.safeParse(state.admin);
      if (!identity.success || !admin.success) {
        const merged: Record<string, string> = {};
        if (!identity.success) Object.assign(merged, fieldErrorsOf(identity.error));
        if (!admin.success) Object.assign(merged, fieldErrorsOf(admin.error));
        setStepErrors(merged);
        return false;
      }
      setStepErrors({});
      return true;
    }
    if (target === 2) {
      if (!state.planCode) {
        setStepErrors({ planCode: "Select a subscription plan to continue." });
        return false;
      }
      setStepErrors({});
      return true;
    }
    setStepErrors({});
    return true;
  };

  const goTo = (target: number) => {
    if (target > step && !validateStep(step)) return;
    setStep(target);
  };

  const submit = async () => {
    if (!validateStep(1) || !validateStep(2)) {
      setStep(1);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const result = await onboardTenant({
        slug: state.identity.slug,
        name: state.identity.name,
        ...(state.identity.brandName ? { brand_name: state.identity.brandName } : {}),
        admin_email: state.admin.adminEmail,
        admin_full_name: state.admin.adminFullName,
        admin_password: state.admin.adminPassword,
        country: state.identity.country.toUpperCase(),
        timezone: state.identity.timezone,
        currency: state.identity.currency.toUpperCase(),
        plan_code: state.planCode,
        enable_omnichannel: state.enableOmnichannel,
        enable_calling: state.enableCalling,
        enable_connectors: state.enableConnectors,
        enable_post_sales: state.enablePostSales,
      });
      setCreated(result);
    } catch (submitError: unknown) {
      setError(errorMessage(submitError, "Failed to onboard the tenant."));
    } finally {
      setSubmitting(false);
    }
  };

  if (created) {
    return <WizardSuccess result={created} onDone={() => navigate("/operator")} />;
  }

  return (
    <div className="space-y-5">
      {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}

      <ol className="grid gap-2 sm:grid-cols-4">
        {WIZARD_STEPS.map((entry) => {
          const isCurrent = entry.id === step;
          const isDone = entry.id < step;
          return (
            <li
              key={entry.id}
              className={`rounded-2xl border p-4 ${
                isCurrent
                  ? "border-forest/30 bg-forest/5"
                  : isDone
                    ? "border-charcoal/10 bg-white"
                    : "border-charcoal/10 bg-white/60"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`grid size-6 place-items-center rounded-full text-[0.65rem] font-bold ${
                    isDone
                      ? "bg-forest text-white"
                      : isCurrent
                        ? "bg-charcoal text-ivory"
                        : "bg-charcoal/10 text-charcoal/55"
                  }`}
                >
                  {isDone ? <Check aria-hidden="true" className="size-3.5" /> : entry.id}
                </span>
                <p className="text-xs font-semibold text-charcoal">{entry.label}</p>
              </div>
              <p className="mt-1.5 text-[0.62rem] leading-4 text-charcoal/50">{entry.hint}</p>
            </li>
          );
        })}
      </ol>

      {step === 1 ? (
        <div className="space-y-5">
          <Surface>
            <SectionHeader
              eyebrow="Step 1 · Workspace"
              title="Identity and locale"
              description="The slug identifies the tenant in deployments and its widget embed URL."
            />
            <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
              <div>
                <label htmlFor="wizard-slug" className={labelClasses}>Tenant slug</label>
                <input
                  id="wizard-slug"
                  value={state.identity.slug}
                  autoComplete="off"
                  placeholder="acme-realty"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({
                      identity: {
                        ...state.identity,
                        slug: event.target.value.trim().toLowerCase(),
                      },
                    })
                  }
                />
                {slugTouched ? (
                  <p
                    className={`mt-1.5 flex items-center gap-1 text-xs ${
                      slugValid ? "text-forest" : "text-clay"
                    }`}
                  >
                    {slugValid ? (
                      <>
                        <Check aria-hidden="true" className="size-3.5" />
                        Valid slug — embed will be /api/v1/widget/{state.identity.slug}/embed.js
                      </>
                    ) : (
                      <>
                        <CircleAlert aria-hidden="true" className="size-3.5" />
                        Lowercase letters, numbers, and hyphens only.
                      </>
                    )}
                  </p>
                ) : null}
                {stepErrors.slug ? <p className="mt-1.5 text-xs text-clay">{stepErrors.slug}</p> : null}
              </div>
              <div>
                <label htmlFor="wizard-name" className={labelClasses}>Organization name</label>
                <input
                  id="wizard-name"
                  value={state.identity.name}
                  placeholder="Acme Realty Private Limited"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ identity: { ...state.identity, name: event.target.value } })
                  }
                />
                {stepErrors.name ? <p className="mt-1.5 text-xs text-clay">{stepErrors.name}</p> : null}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="wizard-brand" className={labelClasses}>
                  Brand name <span className="font-normal text-charcoal/40">(optional)</span>
                </label>
                <input
                  id="wizard-brand"
                  value={state.identity.brandName}
                  placeholder="Defaults to organization name"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ identity: { ...state.identity, brandName: event.target.value } })
                  }
                />
              </div>
              <div>
                <label htmlFor="wizard-country" className={labelClasses}>Country code</label>
                <input
                  id="wizard-country"
                  value={state.identity.country}
                  maxLength={2}
                  className={`${inputClasses} uppercase`}
                  onChange={(event) =>
                    patch({
                      identity: {
                        ...state.identity,
                        country: event.target.value.toUpperCase(),
                      },
                    })
                  }
                />
                {stepErrors.country ? <p className="mt-1.5 text-xs text-clay">{stepErrors.country}</p> : null}
              </div>
              <div>
                <label htmlFor="wizard-currency" className={labelClasses}>Currency</label>
                <input
                  id="wizard-currency"
                  value={state.identity.currency}
                  maxLength={3}
                  className={`${inputClasses} uppercase`}
                  onChange={(event) =>
                    patch({
                      identity: {
                        ...state.identity,
                        currency: event.target.value.toUpperCase(),
                      },
                    })
                  }
                />
                {stepErrors.currency ? <p className="mt-1.5 text-xs text-clay">{stepErrors.currency}</p> : null}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="wizard-timezone" className={labelClasses}>Timezone (IANA)</label>
                <input
                  id="wizard-timezone"
                  value={state.identity.timezone}
                  placeholder="Asia/Kolkata"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ identity: { ...state.identity, timezone: event.target.value } })
                  }
                />
                {stepErrors.timezone ? <p className="mt-1.5 text-xs text-clay">{stepErrors.timezone}</p> : null}
              </div>
            </div>
          </Surface>

          <Surface>
            <SectionHeader
              eyebrow="Step 1 · Administrator"
              title="First tenant admin account"
              description="Credentials are shown once — share them through a secure channel."
            />
            <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
              <div>
                <label htmlFor="wizard-admin-name" className={labelClasses}>Full name</label>
                <input
                  id="wizard-admin-name"
                  value={state.admin.adminFullName}
                  autoComplete="off"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ admin: { ...state.admin, adminFullName: event.target.value } })
                  }
                />
                {stepErrors.adminFullName ? (
                  <p className="mt-1.5 text-xs text-clay">{stepErrors.adminFullName}</p>
                ) : null}
              </div>
              <div>
                <label htmlFor="wizard-admin-email" className={labelClasses}>Email address</label>
                <input
                  id="wizard-admin-email"
                  type="email"
                  value={state.admin.adminEmail}
                  autoComplete="off"
                  placeholder="admin@example.com"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ admin: { ...state.admin, adminEmail: event.target.value } })
                  }
                />
                {stepErrors.adminEmail ? (
                  <p className="mt-1.5 text-xs text-clay">{stepErrors.adminEmail}</p>
                ) : null}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="wizard-admin-password" className={labelClasses}>Temporary password</label>
                <input
                  id="wizard-admin-password"
                  type="password"
                  value={state.admin.adminPassword}
                  autoComplete="new-password"
                  placeholder="At least 12 characters"
                  className={inputClasses}
                  onChange={(event) =>
                    patch({ admin: { ...state.admin, adminPassword: event.target.value } })
                  }
                />
                <p className="mt-1.5 text-xs leading-5 text-charcoal/50">
                  12+ characters with uppercase, lowercase, a number, and a symbol.
                </p>
                {stepErrors.adminPassword ? (
                  <p className="mt-1.5 text-xs text-clay">{stepErrors.adminPassword}</p>
                ) : null}
              </div>
            </div>
          </Surface>
        </div>
      ) : null}

      {step === 2 ? (
        <Surface>
          <SectionHeader
            eyebrow="Step 2 · Subscription"
            title="Pick a plan"
            description="Plans set usage limits and the base feature bundle; individual overrides can be staged later in Tenant 360."
          />
          {plansQuery.isLoading ? (
            <LoadingBlock label="Loading plan catalog…" />
          ) : plansQuery.isError ? (
            <p className="p-5 text-xs text-clay sm:p-6">
              Plans could not be loaded. Go back and retry, or use the advanced form.
            </p>
          ) : plans.filter((plan) => plan.is_active).length === 0 ? (
            <p className="p-5 text-xs leading-5 text-charcoal/60 sm:p-6">
              No active plans exist. Create one under Revenue → Plans &amp;
              Entitlements first, then return to the wizard.
            </p>
          ) : (
            <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-6 lg:grid-cols-3">
              {plans
                .filter((plan) => plan.is_active)
                .map((plan) => {
                  const selected = plan.code === state.planCode;
                  return (
                    <button
                      key={plan.id}
                      type="button"
                      onClick={() => patch({ planCode: plan.code })}
                      aria-pressed={selected}
                      className={`rounded-2xl border p-4 text-left transition-colors ${
                        selected
                          ? "border-forest/40 bg-forest/5"
                          : "border-charcoal/10 bg-white hover:border-charcoal/25"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-charcoal">{plan.name}</p>
                        {selected ? (
                          <span className="grid size-5 place-items-center rounded-full bg-forest text-white">
                            <Check aria-hidden="true" className="size-3" />
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 font-mono text-[0.62rem] text-charcoal/45">{plan.code}</p>
                      <p className="mt-2 text-lg font-semibold text-charcoal">
                        ₹{(plan.price_paise / 100).toLocaleString("en-IN")}
                        <span className="ml-1 text-[0.65rem] font-normal text-charcoal/50">/ month</span>
                      </p>
                      <p className="mt-2 text-[0.65rem] leading-4 text-charcoal/55">
                        {plan.max_users} users · {plan.leads_per_month.toLocaleString("en-IN")} leads ·{" "}
                        {plan.whatsapp_msgs_per_month.toLocaleString("en-IN")} msgs / mo
                      </p>
                    </button>
                  );
                })}
            </div>
          )}
          {stepErrors.planCode ? (
            <p className="px-5 pb-4 text-xs text-clay sm:px-6">{stepErrors.planCode}</p>
          ) : null}
        </Surface>
      ) : null}

      {step === 3 ? (
        <Surface>
          <SectionHeader
            eyebrow="Step 3 · Capabilities"
            title="Opt in to product surfaces"
            description="Each selection is written as a per-tenant feature override and audited (FEATURE_ENABLED)."
          />
          <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-6">
            {FEATURE_OPTINS.map((optin) => {
              const Icon = optin.icon;
              const enabled = state[optin.key];
              return (
                <button
                  key={optin.key}
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  onClick={() => patch({ [optin.key]: !enabled })}
                  className={`flex items-start gap-3 rounded-2xl border p-4 text-left transition-colors ${
                    enabled
                      ? "border-forest/40 bg-forest/5"
                      : "border-charcoal/10 bg-white hover:border-charcoal/25"
                  }`}
                >
                  <span
                    className={`grid size-9 shrink-0 place-items-center rounded-xl ${
                      enabled ? "bg-forest/15 text-forest-deep" : "bg-charcoal/5 text-charcoal/55"
                    }`}
                  >
                    <Icon aria-hidden="true" className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-charcoal">{optin.label}</span>
                      <span
                        className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors ${
                          enabled ? "border-forest/30 bg-forest" : "border-charcoal/20 bg-charcoal/10"
                        }`}
                      >
                        <span
                          aria-hidden="true"
                          className={`size-3.5 rounded-full bg-white shadow-sm transition-transform ${
                            enabled ? "translate-x-4" : "translate-x-0.5"
                          }`}
                        />
                      </span>
                    </span>
                    <span className="mt-1 block text-[0.65rem] leading-4 text-charcoal/55">
                      {optin.hint}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </Surface>
      ) : null}

      {step === 4 ? (
        <Surface>
          <SectionHeader
            eyebrow="Step 4 · Review"
            title="Confirm and provision"
            description="One POST /operator/tenants/onboard call provisions everything below."
          />
          <dl className="grid gap-x-6 gap-y-3 p-5 text-xs sm:grid-cols-2 sm:p-6">
            {[
              ["Organization", state.identity.name],
              ["Slug", state.identity.slug],
              ["Brand", state.identity.brandName || state.identity.name],
              ["Locale", `${state.identity.country} · ${state.identity.currency} · ${state.identity.timezone}`],
              ["Admin", `${state.admin.adminFullName} <${state.admin.adminEmail}>`],
              ["Plan", selectedPlan ? `${selectedPlan.name} (${selectedPlan.code})` : state.planCode],
              [
                "Capabilities",
                [
                  state.enableOmnichannel ? "Omnichannel + WhatsApp" : null,
                  state.enableCalling ? "Calling" : null,
                  state.enableConnectors ? "Connectors" : null,
                  state.enablePostSales ? "Post-sales" : null,
                ]
                  .filter(Boolean)
                  .join(", ") || "Catalog defaults only",
              ],
            ].map(([label, value]) => (
              <div key={label} className="flex flex-col gap-0.5 border-b border-charcoal/5 pb-2">
                <dt className="font-medium text-charcoal/50">{label}</dt>
                <dd className="font-semibold break-all text-charcoal">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="mx-5 mb-5 rounded-xl border border-charcoal/10 bg-[#FAFAF7] p-4 sm:mx-6 sm:mb-6">
            <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
              Expected widget embed
            </p>
            {previewEmbedUrl ? (
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-charcoal/[0.04] px-3 py-2 font-mono text-[0.68rem]">
                  {`<script src="https://<host>${previewEmbedUrl}" async></script>`}
                </code>
                <CopyButton value={previewEmbedUrl} label="Copy path" />
              </div>
            ) : (
              <p className="mt-1.5 text-xs text-charcoal/55">
                Omnichannel is off, so no embed script is served. It can be
                enabled later from Tenant 360 → Entitlements.
              </p>
            )}
          </div>
        </Surface>
      ) : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={onCancel} className={secondaryButtonClasses}>
          Cancel
        </button>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          {step > 1 ? (
            <button type="button" onClick={() => goTo(step - 1)} className={secondaryButtonClasses}>
              <ArrowLeft aria-hidden="true" className="size-3.5" />
              Back
            </button>
          ) : null}
          {step < 4 ? (
            <button type="button" onClick={() => goTo(step + 1)} className={primaryButtonClasses}>
              Continue
              <ArrowRight aria-hidden="true" className="size-3.5" />
            </button>
          ) : (
            <button type="button" disabled={submitting} onClick={() => void submit()} className={primaryButtonClasses}>
              {submitting ? (
                <>
                  <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                  Provisioning workspace…
                </>
              ) : (
                <>
                  <WandSparkles aria-hidden="true" className="size-4" />
                  Provision tenant
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function WizardSuccess({
  result,
  onDone,
}: {
  result: OnboardTenantResponse;
  onDone: () => void;
}) {
  return (
    <Surface className="p-6 text-center sm:p-10">
      <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-forest/10 text-forest">
        <ShieldCheck aria-hidden="true" className="size-6" />
      </span>
      <h2 className="mt-4 text-2xl font-semibold tracking-tight text-charcoal">
        {result.brand_name} is ready
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-charcoal/60">
        The workspace, plan, and starter capabilities were provisioned in one
        audited call. Share the sign-in details securely.
      </p>
      <dl className="mx-auto mt-6 grid max-w-md gap-3 rounded-2xl border border-charcoal/10 bg-charcoal/[0.03] p-5 text-left text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-charcoal/55">Tenant slug</dt>
          <dd className="font-semibold text-charcoal">{result.slug}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-charcoal/55">Admin email</dt>
          <dd className="truncate font-semibold text-charcoal">{result.admin_email}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-charcoal/55">Status</dt>
          <dd className="font-semibold text-forest capitalize">{result.status}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="shrink-0 text-charcoal/55">Enabled features</dt>
          <dd className="text-right text-xs font-semibold text-charcoal">
            {result.enabled_features.length > 0
              ? result.enabled_features.map((key) => key.replaceAll("_", " ")).join(", ")
              : "Catalog defaults only"}
          </dd>
        </div>
        {result.embed_script_url ? (
          <div className="border-t border-charcoal/10 pt-3">
            <dt className="text-charcoal/55">Widget embed</dt>
            <dd className="mt-1.5 flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-charcoal/[0.05] px-2.5 py-1.5 font-mono text-[0.68rem]">
                {result.embed_script_url}
              </code>
              <CopyButton value={result.embed_script_url} />
            </dd>
          </div>
        ) : null}
      </dl>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <Link to={`/operator/tenants/${result.tenant_id}`} className={primaryButtonClasses}>
          <Building2 aria-hidden="true" className="size-4" />
          Open Tenant 360
        </Link>
        <button type="button" onClick={onDone} className={secondaryButtonClasses}>
          Back to Mission Control
        </button>
      </div>
    </Surface>
  );
}

const advancedSchema = identitySchema.extend({
  adminFullName: adminSchema.shape.adminFullName,
  adminEmail: adminSchema.shape.adminEmail,
  adminPassword: adminSchema.shape.adminPassword,
  planId: z.string(),
});

/** Legacy single-shot provisioning kept as the explicit "advanced" path. */
function AdvancedProvisionForm() {
  const navigate = useNavigate();
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });
  const [form, setForm] = useState({
    slug: "",
    name: "",
    brandName: "",
    adminFullName: "",
    adminEmail: "",
    adminPassword: "",
    country: "IN",
    timezone: "Asia/Kolkata",
    currency: "INR",
    planId: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<ProvisionTenantResponse | null>(null);

  const setField = (key: keyof typeof form, value: string) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = advancedSchema.safeParse(form);
    if (!parsed.success) {
      const map: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? "form");
        if (!map[key]) map[key] = issue.message;
      }
      setErrors(map);
      return;
    }
    setErrors({});
    setError(null);
    setSubmitting(true);
    try {
      const values = parsed.data;
      const result = await provisionTenant({
        slug: values.slug,
        name: values.name,
        ...(values.brandName ? { brand_name: values.brandName } : {}),
        admin_email: values.adminEmail,
        admin_full_name: values.adminFullName,
        admin_password: values.adminPassword,
        country: values.country.toUpperCase(),
        timezone: values.timezone,
        currency: values.currency.toUpperCase(),
        ...(isUuidLike(values.planId) ? { plan_id: values.planId } : {}),
      });
      setCreated(result);
    } catch (submitError: unknown) {
      setError(errorMessage(submitError, "Failed to provision the tenant."));
    } finally {
      setSubmitting(false);
    }
  };

  if (created) {
    return (
      <Surface className="p-6 text-center sm:p-10">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-forest/10 text-forest">
          <ShieldCheck aria-hidden="true" className="size-6" />
        </span>
        <h2 className="mt-4 text-2xl font-semibold tracking-tight text-charcoal">
          {created.brand_name} is ready
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-charcoal/60">
          Workspace and administrator provisioned. Share the credentials with{" "}
          {created.admin_email} through a secure channel.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <Link to={`/operator/tenants/${created.id}`} className={primaryButtonClasses}>
            Open Tenant 360
          </Link>
          <button type="button" onClick={() => navigate("/operator")} className={secondaryButtonClasses}>
            Back to Mission Control
          </button>
        </div>
      </Surface>
    );
  }

  const fields: {
    key: keyof typeof form;
    label: string;
    placeholder?: string;
    type?: string;
    maxLength?: number;
    uppercase?: boolean;
    optional?: boolean;
  }[] = [
    { key: "slug", label: "Tenant slug", placeholder: "acme-realty" },
    { key: "name", label: "Organization name", placeholder: "Acme Realty Private Limited" },
    { key: "brandName", label: "Brand name", optional: true },
    { key: "adminFullName", label: "Admin full name" },
    { key: "adminEmail", label: "Admin email", type: "email", placeholder: "admin@example.com" },
    { key: "adminPassword", label: "Temporary password", type: "password", placeholder: "At least 12 characters" },
    { key: "country", label: "Country code", maxLength: 2, uppercase: true },
    { key: "timezone", label: "Timezone", placeholder: "Asia/Kolkata" },
    { key: "currency", label: "Currency", maxLength: 3, uppercase: true },
  ];

  return (
    <form noValidate onSubmit={submit} className="space-y-5">
      {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
      <Surface>
        <SectionHeader
          eyebrow="Direct provisioning"
          title="POST /operator/tenants"
          description="Provisions the workspace and admin account without starter feature overrides."
        />
        <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
          {fields.map((field) => (
            <div key={field.key} className={field.key === "adminPassword" ? "sm:col-span-2" : ""}>
              <label htmlFor={`advanced-${field.key}`} className={labelClasses}>
                {field.label}
                {field.optional ? (
                  <span className="font-normal text-charcoal/40"> (optional)</span>
                ) : null}
              </label>
              <input
                id={`advanced-${field.key}`}
                type={field.type ?? "text"}
                value={form[field.key]}
                placeholder={field.placeholder}
                maxLength={field.maxLength}
                autoComplete={field.type === "password" ? "new-password" : "off"}
                className={`${inputClasses} ${field.uppercase ? "uppercase" : ""}`}
                onChange={(event) =>
                  setField(
                    field.key,
                    field.uppercase ? event.target.value.toUpperCase() : event.target.value,
                  )
                }
              />
              {errors[field.key] ? (
                <p className="mt-1.5 text-xs text-clay">{errors[field.key]}</p>
              ) : null}
            </div>
          ))}
          <div className="sm:col-span-2">
            <label htmlFor="advanced-plan" className={labelClasses}>Subscription plan</label>
            <select
              id="advanced-plan"
              value={form.planId}
              className={inputClasses}
              onChange={(event) => setField("planId", event.target.value)}
            >
              <option value="">No plan assigned</option>
              {(plansQuery.data ?? [])
                .filter((plan) => plan.is_active)
                .map((plan) => (
                  <option key={plan.id} value={plan.id}>{plan.name}</option>
                ))}
            </select>
          </div>
        </div>
      </Surface>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button type="button" onClick={() => navigate("/operator")} className={secondaryButtonClasses}>
          Cancel
        </button>
        <button type="submit" disabled={submitting} className={`${primaryButtonClasses} min-h-11 px-6`}>
          {submitting ? (
            <>
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              Provisioning workspace…
            </>
          ) : (
            <>
              <Building2 aria-hidden="true" className="size-4" />
              Provision tenant
            </>
          )}
        </button>
      </div>
    </form>
  );
}
