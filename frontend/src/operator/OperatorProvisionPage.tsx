import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ArrowLeft, Building2, LoaderCircle, ShieldCheck } from "lucide-react";
import { fetchOperatorPlans, provisionTenant } from "./api";
import { errorMessage } from "../shared/apiRequest";
import type { ProvisionTenantResponse } from "./operatorModel";
import {
  InlineNotice,
  SectionHeader,
  Surface,
  inputClasses,
  labelClasses,
  primaryButtonClasses,
} from "./ui";

const provisionSchema = z.object({
  slug: z
    .string()
    .trim()
    .min(2, "Enter a tenant slug.")
    .max(100)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and hyphens."),
  name: z.string().trim().min(2, "Enter the legal organization name.").max(255),
  brandName: z.string().trim().max(255),
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
  country: z.string().trim().length(2, "Use a two-letter country code."),
  timezone: z.string().trim().min(1, "Enter an IANA timezone."),
  currency: z.string().trim().length(3, "Use a three-letter currency code."),
  planId: z.string(),
});

type ProvisionValues = z.infer<typeof provisionSchema>;

export function OperatorProvisionPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<ProvisionTenantResponse | null>(null);
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ProvisionValues>({
    resolver: zodResolver(provisionSchema),
    defaultValues: {
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
    },
  });

  const onSubmit = async (values: ProvisionValues) => {
    setError(null);
    try {
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
        ...(values.planId ? { plan_id: values.planId } : {}),
      });
      setCreated(result);
    } catch (submitError: unknown) {
      setError(errorMessage(submitError, "Failed to provision the tenant."));
    }
  };

  const fieldError = (message?: string) =>
    message ? <p className="mt-1.5 text-xs text-clay">{message}</p> : null;

  if (created) {
    return (
      <div className="mx-auto max-w-2xl">
        <Surface className="p-6 text-center sm:p-10">
          <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-forest/10 text-forest">
            <ShieldCheck aria-hidden="true" className="size-6" />
          </span>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight text-charcoal">
            {created.brand_name} is ready
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-charcoal/60">
            The tenant workspace and its administrator account have been
            provisioned. Share the sign-in details with {created.admin_email}{" "}
            through a secure channel.
          </p>
          <dl className="mx-auto mt-6 grid max-w-sm gap-3 rounded-2xl border border-charcoal/10 bg-charcoal/[0.03] p-5 text-left text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-charcoal/55">Tenant slug</dt>
              <dd className="font-semibold text-charcoal">{created.slug}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-charcoal/55">Admin email</dt>
              <dd className="truncate font-semibold text-charcoal">{created.admin_email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-charcoal/55">Status</dt>
              <dd className="font-semibold text-forest capitalize">{created.status}</dd>
            </div>
          </dl>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Link to={`/operator/tenants/${created.id}`} className={primaryButtonClasses}>
              Open tenant
            </Link>
            <button
              type="button"
              onClick={() => navigate("/operator")}
              className="inline-flex min-h-10 items-center justify-center rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal/75"
            >
              Back to tenants
            </button>
          </div>
        </Surface>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        to="/operator"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal/60 transition-colors hover:text-charcoal"
      >
        <ArrowLeft aria-hidden="true" className="size-3.5" />
        Back to tenants
      </Link>
      <h1 className="mt-4 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
        Provision a tenant
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
        Create an isolated workspace, its public brand identity, and the first
        tenant administrator in one step.
      </p>

      <form noValidate onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-5">
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}

        <Surface>
          <SectionHeader
            eyebrow="Workspace identity"
            title="Tenant details"
            description="The slug identifies the tenant in its deployment and API configuration."
          />
          <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
            <div>
              <label htmlFor="tenant-slug" className={labelClasses}>Tenant slug</label>
              <input
                id="tenant-slug"
                placeholder="acme-realty"
                autoComplete="off"
                className={inputClasses}
                {...register("slug")}
                onBlur={(event) => {
                  if (!event.target.value) return;
                  setValue("slug", event.target.value.trim().toLowerCase());
                }}
              />
              {fieldError(errors.slug?.message)}
            </div>
            <div>
              <label htmlFor="tenant-name" className={labelClasses}>Organization name</label>
              <input
                id="tenant-name"
                placeholder="Acme Realty Private Limited"
                className={inputClasses}
                {...register("name")}
              />
              {fieldError(errors.name?.message)}
            </div>
            <div>
              <label htmlFor="tenant-brand" className={labelClasses}>
                Brand name <span className="font-normal text-charcoal/40">(optional)</span>
              </label>
              <input
                id="tenant-brand"
                placeholder="Defaults to organization name"
                className={inputClasses}
                {...register("brandName")}
              />
              {fieldError(errors.brandName?.message)}
            </div>
            <div>
              <label htmlFor="tenant-plan" className={labelClasses}>Subscription plan</label>
              <select id="tenant-plan" className={inputClasses} {...register("planId")}>
                <option value="">No plan assigned</option>
                {(plansQuery.data ?? [])
                  .filter((plan) => plan.is_active)
                  .map((plan) => (
                    <option key={plan.id} value={plan.id}>{plan.name}</option>
                  ))}
              </select>
              {plansQuery.isError ? (
                <p className="mt-1.5 text-xs text-clay">
                  Plans could not be loaded. You can still provision without one.
                </p>
              ) : null}
            </div>
          </div>
        </Surface>

        <Surface>
          <SectionHeader
            eyebrow="Regional configuration"
            title="Locale and currency"
          />
          <div className="grid gap-4 p-5 sm:grid-cols-3 sm:p-6">
            <div>
              <label htmlFor="tenant-country" className={labelClasses}>Country code</label>
              <input
                id="tenant-country"
                maxLength={2}
                placeholder="IN"
                className={`${inputClasses} uppercase`}
                {...register("country")}
              />
              {fieldError(errors.country?.message)}
            </div>
            <div>
              <label htmlFor="tenant-timezone" className={labelClasses}>Timezone</label>
              <input
                id="tenant-timezone"
                placeholder="Asia/Kolkata"
                className={inputClasses}
                {...register("timezone")}
              />
              {fieldError(errors.timezone?.message)}
            </div>
            <div>
              <label htmlFor="tenant-currency" className={labelClasses}>Currency</label>
              <input
                id="tenant-currency"
                maxLength={3}
                placeholder="INR"
                className={`${inputClasses} uppercase`}
                {...register("currency")}
              />
              {fieldError(errors.currency?.message)}
            </div>
          </div>
        </Surface>

        <Surface>
          <SectionHeader
            eyebrow="First administrator"
            title="Tenant admin account"
            description="The administrator can manage users, projects, messaging, and branding for this tenant only."
          />
          <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
            <div>
              <label htmlFor="tenant-admin-name" className={labelClasses}>Full name</label>
              <input
                id="tenant-admin-name"
                autoComplete="off"
                placeholder="Admin full name"
                className={inputClasses}
                {...register("adminFullName")}
              />
              {fieldError(errors.adminFullName?.message)}
            </div>
            <div>
              <label htmlFor="tenant-admin-email" className={labelClasses}>Email address</label>
              <input
                id="tenant-admin-email"
                type="email"
                autoComplete="off"
                placeholder="admin@example.com"
                className={inputClasses}
                {...register("adminEmail")}
              />
              {fieldError(errors.adminEmail?.message)}
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="tenant-admin-password" className={labelClasses}>Temporary password</label>
              <input
                id="tenant-admin-password"
                type="password"
                autoComplete="new-password"
                placeholder="At least 12 characters"
                className={inputClasses}
                {...register("adminPassword")}
              />
              <p className="mt-1.5 text-xs leading-5 text-charcoal/50">
                Use at least 12 characters with uppercase, lowercase, a number,
                and a symbol. Share it securely with the administrator.
              </p>
              {fieldError(errors.adminPassword?.message)}
            </div>
          </div>
        </Surface>

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Link
            to="/operator"
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-charcoal/15 bg-white px-5 text-xs font-semibold text-charcoal/70"
          >
            Cancel
          </Link>
          <button type="submit" disabled={isSubmitting} className={`${primaryButtonClasses} min-h-11 px-6`}>
            {isSubmitting ? (
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
    </div>
  );
}
