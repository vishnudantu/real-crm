import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";
import {
  Check,
  CreditCard,
  LoaderCircle,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import {
  createOperatorPlan,
  fetchOperatorPlans,
  updateOperatorPlan,
} from "./api";
import { useOperator } from "./OperatorAuthGuard";
import { errorMessage } from "../shared/apiRequest";
import {
  featureRecordToRows,
  featureRowsToRecord,
  formatInrFromPaise,
  paiseToRupeesInput,
  rupeesInputToPaise,
} from "./format";
import type { OperatorPlan, PlanFormValues } from "./operatorModel";
import {
  ErrorBlock,
  InlineNotice,
  LoadingBlock,
  Modal,
  SectionHeader,
  Surface,
  inputClasses,
  labelClasses,
  primaryButtonClasses,
  secondaryButtonClasses,
} from "./ui";

const planSchema = z.object({
  code: z
    .string()
    .trim()
    .min(1, "Enter a plan code.")
    .max(64)
    .regex(/^[a-z0-9_]+$/, "Use lowercase letters, numbers, and underscores."),
  name: z.string().trim().min(1, "Enter a plan name.").max(128),
  description: z.string().trim().max(2000),
  priceRupees: z
    .string()
    .trim()
    .min(1, "Enter a monthly price.")
    .refine((value) => Number.isFinite(rupeesInputToPaise(value)), {
      message: "Enter a non-negative amount with up to two decimal places.",
    }),
  maxUsers: z.number().int().min(1, "Allow at least one user."),
  leadsPerMonth: z.number().int().min(1, "Allow at least one lead."),
  whatsappMsgsPerMonth: z.number().int().min(1, "Allow at least one message."),
  featureRows: z.array(z.object({ key: z.string(), value: z.string() })),
  isActive: z.boolean(),
});

export function OperatorPlansPage() {
  const { can } = useOperator();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<OperatorPlan | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });
  const plans = plansQuery.data ?? [];
  const activeCount = plans.filter((plan) => plan.is_active).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Commercial catalog
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Subscription plans
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-charcoal/60">
            Set monthly INR pricing, workspace limits, and feature entitlements
            for tenant subscriptions.
          </p>
        </div>
        {can("plans.write") ? (
          <button
            type="button"
            onClick={() => {
              setNotice(null);
              setEditing("new");
            }}
            className={primaryButtonClasses}
          >
            <Plus aria-hidden="true" className="size-4" />
            Create plan
          </button>
        ) : null}
      </div>

      {notice ? <InlineNotice tone="success">{notice}</InlineNotice> : null}

      <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-2xl border border-charcoal/10 bg-white px-5 py-4 text-xs text-charcoal/60 shadow-xs">
        <span><strong className="text-charcoal">{plans.length}</strong> total plans</span>
        <span><strong className="text-forest">{activeCount}</strong> active plans</span>
        <span><strong className="text-charcoal">{plans.length - activeCount}</strong> inactive plans</span>
      </div>

      <Surface>
        <SectionHeader
          eyebrow="Plan directory"
          title="Pricing and entitlements"
          description="Prices are displayed in Indian rupees and stored as integer paise."
        />
        {plansQuery.isLoading ? (
          <LoadingBlock label="Loading subscription plans…" />
        ) : plansQuery.isError ? (
          <ErrorBlock
            message={
              plansQuery.error instanceof Error
                ? plansQuery.error.message
                : "Failed to load plans."
            }
            onRetry={() => void plansQuery.refetch()}
          />
        ) : plans.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-12 text-center">
            <span className="grid size-11 place-items-center rounded-2xl bg-charcoal/5 text-charcoal/45">
              <CreditCard aria-hidden="true" className="size-5" />
            </span>
            <p className="mt-3 text-sm font-semibold text-charcoal">No plans yet</p>
            <p className="mt-1 text-xs text-charcoal/55">
              Create the first plan to make it available during tenant provisioning.
            </p>
          </div>
        ) : (
          <div className="grid gap-px overflow-hidden rounded-b-2xl bg-charcoal/10 md:grid-cols-2 xl:grid-cols-3">
            {plans.map((plan) => (
              <article key={plan.id} className="flex flex-col bg-white p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-semibold text-charcoal">{plan.name}</h2>
                      {!plan.is_active ? (
                        <span className="rounded-full bg-charcoal/10 px-2 py-0.5 text-[0.6rem] font-semibold text-charcoal/55 uppercase">
                          Inactive
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 font-mono text-[0.65rem] text-charcoal/45">{plan.code}</p>
                  </div>
                  {can("plans.write") ? (
                    <button
                      type="button"
                      onClick={() => {
                        setNotice(null);
                        setEditing(plan);
                      }}
                      aria-label={`Edit ${plan.name}`}
                      className="rounded-lg border border-charcoal/10 p-2 text-charcoal/60 transition-colors hover:bg-charcoal/5 hover:text-charcoal"
                    >
                      <Pencil aria-hidden="true" className="size-3.5" />
                    </button>
                  ) : null}
                </div>

                <p className="mt-4 text-3xl font-semibold tracking-tight text-charcoal">
                  {formatInrFromPaise(plan.price_paise)}
                  <span className="ml-1 text-xs font-normal text-charcoal/50">/ month</span>
                </p>
                <p className="mt-2 min-h-10 text-xs leading-5 text-charcoal/60">
                  {plan.description || "No plan description."}
                </p>

                <dl className="mt-5 space-y-2.5 border-t border-charcoal/10 pt-4 text-xs">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-charcoal/55">Users</dt>
                    <dd className="font-semibold">{plan.max_users.toLocaleString("en-IN")}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-charcoal/55">Leads / month</dt>
                    <dd className="font-semibold">{plan.leads_per_month.toLocaleString("en-IN")}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-charcoal/55">WhatsApp / month</dt>
                    <dd className="font-semibold">{plan.whatsapp_msgs_per_month.toLocaleString("en-IN")}</dd>
                  </div>
                </dl>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  {Object.entries(plan.features).slice(0, 5).map(([key, value]) => (
                    <span
                      key={key}
                      className="inline-flex items-center gap-1 rounded-md border border-forest/15 bg-forest/5 px-2 py-1 text-[0.62rem] font-medium text-forest-deep"
                    >
                      <Check aria-hidden="true" className="size-3" />
                      {key.replaceAll("_", " ")}
                      {value !== true && value !== "" ? `: ${String(value)}` : ""}
                    </span>
                  ))}
                  {Object.keys(plan.features).length === 0 ? (
                    <span className="text-[0.65rem] text-charcoal/45">No additional feature flags</span>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </Surface>

      {editing ? (
        <PlanEditorModal
          plan={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (message) => {
            setEditing(null);
            setNotice(message);
            await queryClient.invalidateQueries({ queryKey: ["operator", "plans"] });
          }}
        />
      ) : null}
    </div>
  );
}

interface PlanEditorModalProps {
  plan: OperatorPlan | null;
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}

function PlanEditorModal({ plan, onClose, onSaved }: PlanEditorModalProps) {
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PlanFormValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      code: plan?.code ?? "",
      name: plan?.name ?? "",
      description: plan?.description ?? "",
      priceRupees: plan ? paiseToRupeesInput(plan.price_paise) : "",
      maxUsers: plan?.max_users ?? 10,
      leadsPerMonth: plan?.leads_per_month ?? 1000,
      whatsappMsgsPerMonth: plan?.whatsapp_msgs_per_month ?? 1000,
      featureRows: plan ? featureRecordToRows(plan.features) : [],
      isActive: plan?.is_active ?? true,
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "featureRows" });

  const mutation = useMutation({
    mutationFn: async (values: PlanFormValues) => {
      const features = featureRowsToRecord(values.featureRows);
      const pricePaise = rupeesInputToPaise(values.priceRupees);
      const description = values.description.trim() || null;

      if (plan) {
        return updateOperatorPlan(plan.id, {
          name: values.name.trim(),
          description,
          price_paise: pricePaise,
          max_users: values.maxUsers,
          leads_per_month: values.leadsPerMonth,
          whatsapp_msgs_per_month: values.whatsappMsgsPerMonth,
          features,
          is_active: values.isActive,
        });
      }

      return createOperatorPlan({
        code: values.code.trim(),
        name: values.name.trim(),
        description,
        price_paise: pricePaise,
        currency: "INR",
        max_users: values.maxUsers,
        leads_per_month: values.leadsPerMonth,
        whatsapp_msgs_per_month: values.whatsappMsgsPerMonth,
        features,
        is_active: values.isActive,
      });
    },
    onSuccess: async (saved) => {
      await onSaved(plan ? `${saved.name} updated successfully.` : `${saved.name} created successfully.`);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to save the plan."));
    },
  });

  return (
    <Modal
      title={plan ? `Edit ${plan.name}` : "Create subscription plan"}
      description="Define monthly pricing, usage limits, and optional feature flags."
      onClose={onClose}
      widthClass="max-w-3xl"
    >
      <form noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="plan-code" className={labelClasses}>Plan code</label>
            <input
              id="plan-code"
              placeholder="growth"
              disabled={Boolean(plan)}
              className={inputClasses}
              {...register("code")}
            />
            {errors.code ? <p className="mt-1.5 text-xs text-clay">{errors.code.message}</p> : null}
          </div>
          <div>
            <label htmlFor="plan-name" className={labelClasses}>Display name</label>
            <input id="plan-name" placeholder="Growth" className={inputClasses} {...register("name")} />
            {errors.name ? <p className="mt-1.5 text-xs text-clay">{errors.name.message}</p> : null}
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="plan-description" className={labelClasses}>Description (optional)</label>
            <textarea
              id="plan-description"
              rows={2}
              placeholder="For growing real-estate teams that need automation…"
              className={`${inputClasses} resize-y`}
              {...register("description")}
            />
            {errors.description ? <p className="mt-1.5 text-xs text-clay">{errors.description.message}</p> : null}
          </div>
          <div>
            <label htmlFor="plan-price" className={labelClasses}>Monthly price (INR)</label>
            <div className="relative">
              <span className="absolute top-1/2 left-3.5 -translate-y-1/2 text-sm text-charcoal/45">₹</span>
              <input
                id="plan-price"
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                placeholder="1499"
                className={`${inputClasses} pl-8`}
                {...register("priceRupees")}
              />
            </div>
            {errors.priceRupees ? <p className="mt-1.5 text-xs text-clay">{errors.priceRupees.message}</p> : null}
          </div>
          <div>
            <label htmlFor="plan-users" className={labelClasses}>Maximum users</label>
            <input
              id="plan-users"
              type="number"
              min="1"
              step="1"
              className={inputClasses}
              {...register("maxUsers", { valueAsNumber: true })}
            />
            {errors.maxUsers ? <p className="mt-1.5 text-xs text-clay">{errors.maxUsers.message}</p> : null}
          </div>
          <div>
            <label htmlFor="plan-leads" className={labelClasses}>Leads per month</label>
            <input
              id="plan-leads"
              type="number"
              min="1"
              step="1"
              className={inputClasses}
              {...register("leadsPerMonth", { valueAsNumber: true })}
            />
            {errors.leadsPerMonth ? <p className="mt-1.5 text-xs text-clay">{errors.leadsPerMonth.message}</p> : null}
          </div>
          <div>
            <label htmlFor="plan-whatsapp" className={labelClasses}>WhatsApp messages per month</label>
            <input
              id="plan-whatsapp"
              type="number"
              min="1"
              step="1"
              className={inputClasses}
              {...register("whatsappMsgsPerMonth", { valueAsNumber: true })}
            />
            {errors.whatsappMsgsPerMonth ? <p className="mt-1.5 text-xs text-clay">{errors.whatsappMsgsPerMonth.message}</p> : null}
          </div>
        </div>

        <div className="mt-5 border-t border-charcoal/10 pt-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-xs font-semibold text-charcoal">Feature flags</h3>
              <p className="mt-0.5 text-[0.65rem] text-charcoal/50">
                Leave a value blank to store the flag as enabled (true).
              </p>
            </div>
            <button
              type="button"
              onClick={() => append({ key: "", value: "" })}
              className="inline-flex items-center gap-1 text-xs font-semibold text-forest"
            >
              <Plus aria-hidden="true" className="size-3.5" />
              Add feature
            </button>
          </div>
          {fields.length > 0 ? (
            <div className="mt-3 space-y-2">
              {fields.map((field, index) => (
                <div key={field.id} className="flex gap-2">
                  <input
                    aria-label={`Feature ${index + 1} key`}
                    placeholder="feature_key"
                    className={`${inputClasses} mt-0`}
                    {...register(`featureRows.${index}.key`)}
                  />
                  <input
                    aria-label={`Feature ${index + 1} value`}
                    placeholder="true"
                    className={`${inputClasses} mt-0`}
                    {...register(`featureRows.${index}.value`)}
                  />
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    aria-label={`Remove feature ${index + 1}`}
                    className="grid size-10 shrink-0 place-items-center rounded-xl border border-charcoal/10 text-charcoal/45 hover:bg-clay-soft hover:text-clay"
                  >
                    <Trash2 aria-hidden="true" className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <label className="mt-5 flex cursor-pointer items-center gap-2.5 text-xs font-semibold text-charcoal">
          <input
            type="checkbox"
            className="size-4 rounded border-charcoal/25 accent-forest"
            {...register("isActive")}
          />
          Plan is available for tenant provisioning
        </label>

        <div className="mt-6 flex flex-col-reverse gap-3 border-t border-charcoal/10 pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className={secondaryButtonClasses}>
            <X aria-hidden="true" className="size-3.5" />
            Cancel
          </button>
          <button type="submit" disabled={isSubmitting || mutation.isPending} className={primaryButtonClasses}>
            {isSubmitting || mutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            ) : null}
            {plan ? "Save plan changes" : "Create plan"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
