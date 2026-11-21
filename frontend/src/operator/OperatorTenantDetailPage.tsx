import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarDays,
  Cloud,
  LoaderCircle,
  MailCheck,
  PauseCircle,
  PlayCircle,
  Users,
} from "lucide-react";
import {
  fetchOperatorPlans,
  fetchOperatorTenant,
  requestTenantDeployment,
  updateTenantStatus,
} from "./api";
import { useOperator } from "./OperatorAuthGuard";
import { errorMessage } from "../shared/apiRequest";
import { formatInrFromPaise } from "./format";
import type { DeploymentProvider } from "./operatorModel";
import {
  ErrorBlock,
  InlineNotice,
  LoadingBlock,
  Modal,
  SectionHeader,
  StatusBadge,
  Surface,
  inputClasses,
  labelClasses,
  primaryButtonClasses,
} from "./ui";

export function OperatorTenantDetailPage() {
  const { tenantId = "" } = useParams<{ tenantId: string }>();
  const { can } = useOperator();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [deploymentOpen, setDeploymentOpen] = useState(false);

  const tenantQuery = useQuery({
    queryKey: ["operator", "tenants", tenantId],
    queryFn: () => fetchOperatorTenant(tenantId),
    enabled: Boolean(tenantId),
  });
  const plansQuery = useQuery({
    queryKey: ["operator", "plans"],
    queryFn: fetchOperatorPlans,
  });

  const statusMutation = useMutation({
    mutationFn: (status: "active" | "suspended") =>
      updateTenantStatus(tenantId, status),
    onSuccess: async (_, status) => {
      setNotice({
        tone: "success",
        text: status === "active" ? "Tenant activated successfully." : "Tenant suspended successfully.",
      });
      await queryClient.invalidateQueries({ queryKey: ["operator", "tenants"] });
    },
    onError: (error: unknown) => {
      setNotice({ tone: "error", text: errorMessage(error, "Failed to update tenant status.") });
    },
  });

  const tenant = tenantQuery.data;
  const plan = (plansQuery.data ?? []).find((item) => item.id === tenant?.plan_id);

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/operator"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal/60 transition-colors hover:text-charcoal"
        >
          <ArrowLeft aria-hidden="true" className="size-3.5" />
          Back to tenants
        </Link>
      </div>

      {tenantQuery.isLoading ? (
        <Surface><LoadingBlock label="Loading tenant details…" /></Surface>
      ) : tenantQuery.isError || !tenant ? (
        <Surface>
          <ErrorBlock
            message={
              tenantQuery.error instanceof Error
                ? tenantQuery.error.message
                : "Tenant not found."
            }
            onRetry={() => void tenantQuery.refetch()}
          />
        </Surface>
      ) : (
        <>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-center gap-4">
              <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-charcoal text-xl font-bold text-ivory">
                {tenant.brand_name.charAt(0).toUpperCase()}
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <h1 className="text-2xl font-semibold tracking-tight text-charcoal">
                    {tenant.brand_name}
                  </h1>
                  <StatusBadge status={tenant.status} />
                </div>
                <p className="mt-1 text-sm text-charcoal/55">
                  {tenant.name} · <span className="font-mono text-xs">{tenant.slug}</span>
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {can("deployments.write") ? (
                <button
                  type="button"
                  onClick={() => setDeploymentOpen(true)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-charcoal/15 bg-white px-4 text-xs font-semibold text-charcoal/75 transition-colors hover:bg-charcoal/5"
                >
                  <Cloud aria-hidden="true" className="size-4" />
                  Request deployment
                </button>
              ) : null}
              {can("tenants.write") ? (
                <button
                  type="button"
                  disabled={statusMutation.isPending}
                  onClick={() => {
                    setNotice(null);
                    statusMutation.mutate(tenant.status === "active" ? "suspended" : "active");
                  }}
                  className={`inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-xs font-semibold transition-colors disabled:opacity-60 ${
                    tenant.status === "active"
                      ? "border border-clay/25 bg-clay-soft text-clay hover:bg-clay-soft/70"
                      : "bg-forest text-white hover:bg-forest-deep"
                  }`}
                >
                  {statusMutation.isPending ? (
                    <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                  ) : tenant.status === "active" ? (
                    <PauseCircle aria-hidden="true" className="size-4" />
                  ) : (
                    <PlayCircle aria-hidden="true" className="size-4" />
                  )}
                  {tenant.status === "active" ? "Suspend tenant" : "Activate tenant"}
                </button>
              ) : null}
            </div>
          </div>

          {notice ? <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice> : null}

          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            {[
              { label: "Users", value: tenant.users, icon: Users },
              { label: "Leads", value: tenant.leads, icon: Users },
              { label: "Bookings", value: tenant.bookings, icon: CalendarDays },
              { label: "Messages sent", value: tenant.deliveries, icon: MailCheck },
            ].map((metric) => {
              const Icon = metric.icon;
              return (
                <div key={metric.label} className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs sm:p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                      {metric.label}
                    </p>
                    <Icon aria-hidden="true" className="size-4 text-charcoal/35" />
                  </div>
                  <p className="mt-2 text-2xl font-semibold tracking-tight text-charcoal">
                    {metric.value.toLocaleString("en-IN")}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <Surface>
              <SectionHeader eyebrow="Configuration" title="Workspace settings" />
              <dl className="divide-y divide-charcoal/5 px-5 sm:px-6">
                {[
                  ["Tenant ID", tenant.id],
                  ["Slug", tenant.slug],
                  ["Country", tenant.country],
                  ["Timezone", tenant.timezone],
                  ["Currency", tenant.currency],
                ].map(([label, value]) => (
                  <div key={label} className="flex flex-col gap-1 py-3.5 text-xs sm:flex-row sm:items-center sm:justify-between">
                    <dt className="font-medium text-charcoal/55">{label}</dt>
                    <dd className="font-mono text-[0.7rem] break-all text-charcoal">{value}</dd>
                  </div>
                ))}
              </dl>
            </Surface>

            <Surface>
              <SectionHeader eyebrow="Subscription" title={plan?.name ?? "No plan assigned"} />
              {plan ? (
                <div className="p-5 sm:p-6">
                  <p className="text-3xl font-semibold tracking-tight text-charcoal">
                    {formatInrFromPaise(plan.price_paise)}
                    <span className="ml-1 text-xs font-normal text-charcoal/50">/ month</span>
                  </p>
                  <p className="mt-2 text-xs leading-5 text-charcoal/60">
                    {plan.description ?? "No plan description provided."}
                  </p>
                  <dl className="mt-5 space-y-3 border-t border-charcoal/10 pt-4 text-xs">
                    <div className="flex justify-between gap-4">
                      <dt className="text-charcoal/55">Maximum users</dt>
                      <dd className="font-semibold">{plan.max_users.toLocaleString("en-IN")}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-charcoal/55">Leads per month</dt>
                      <dd className="font-semibold">{plan.leads_per_month.toLocaleString("en-IN")}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-charcoal/55">WhatsApp messages</dt>
                      <dd className="font-semibold">{plan.whatsapp_msgs_per_month.toLocaleString("en-IN")} / month</dd>
                    </div>
                  </dl>
                  <Link
                    to="/operator/plans"
                    className="mt-5 inline-flex text-xs font-semibold text-forest hover:text-forest-deep"
                  >
                    Manage subscription plans →
                  </Link>
                </div>
              ) : (
                <p className="p-6 text-sm leading-6 text-charcoal/60">
                  This tenant is not linked to a subscription plan. Contact a
                  platform owner to update its plan assignment.
                </p>
              )}
            </Surface>
          </div>
        </>
      )}

      {tenant && deploymentOpen ? (
        <DeploymentModal
          tenantId={tenant.id}
          tenantName={tenant.brand_name}
          onClose={() => setDeploymentOpen(false)}
          onRequested={(message) => {
            setDeploymentOpen(false);
            setNotice({ tone: "success", text: message });
          }}
        />
      ) : null}
    </div>
  );
}

interface DeploymentModalProps {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
  onRequested: (message: string) => void;
}

function DeploymentModal({
  tenantId,
  tenantName,
  onClose,
  onRequested,
}: DeploymentModalProps) {
  const [provider, setProvider] = useState<DeploymentProvider>("railway");
  const [environment, setEnvironment] = useState("production");
  const [region, setRegion] = useState("");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      requestTenantDeployment(tenantId, {
        provider,
        environment: environment.trim(),
        ...(region.trim() ? { region: region.trim() } : {}),
        ...(repositoryUrl.trim() ? { repository_url: repositoryUrl.trim() } : {}),
        ...(apiBaseUrl.trim() ? { api_base_url: apiBaseUrl.trim() } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      }),
    onSuccess: (deployment) => {
      onRequested(
        `Deployment ${deployment.id.slice(0, 8)} requested with status ${deployment.status}.`,
      );
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to request deployment."));
    },
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!environment.trim()) {
      setError("Enter an environment name.");
      return;
    }
    setError(null);
    mutation.mutate();
  };

  return (
    <Modal
      title="Request deployment"
      description={`Create a deployment request for ${tenantName}.`}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="deployment-provider" className={labelClasses}>Provider</label>
            <select
              id="deployment-provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value as DeploymentProvider)}
              className={inputClasses}
            >
              <option value="railway">Railway</option>
              <option value="render">Render</option>
              <option value="aws">AWS</option>
              <option value="local">Local</option>
              <option value="manual">Manual</option>
            </select>
          </div>
          <div>
            <label htmlFor="deployment-environment" className={labelClasses}>Environment</label>
            <input
              id="deployment-environment"
              value={environment}
              onChange={(event) => setEnvironment(event.target.value)}
              maxLength={64}
              className={inputClasses}
            />
          </div>
          <div>
            <label htmlFor="deployment-region" className={labelClasses}>Region (optional)</label>
            <input
              id="deployment-region"
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              placeholder="ap-south-1"
              maxLength={64}
              className={inputClasses}
            />
          </div>
          <div>
            <label htmlFor="deployment-api-url" className={labelClasses}>API base URL (optional)</label>
            <input
              id="deployment-api-url"
              type="url"
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              placeholder="https://api.example.com/api/v1"
              className={inputClasses}
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="deployment-repository" className={labelClasses}>Repository URL (optional)</label>
            <input
              id="deployment-repository"
              type="url"
              value={repositoryUrl}
              onChange={(event) => setRepositoryUrl(event.target.value)}
              placeholder="https://github.com/organization/repository"
              className={inputClasses}
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="deployment-notes" className={labelClasses}>Notes (optional)</label>
            <textarea
              id="deployment-notes"
              rows={3}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              maxLength={2000}
              placeholder="Deployment context, release version, or handoff notes…"
              className={`${inputClasses} resize-y`}
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3 border-t border-charcoal/10 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal/70"
          >
            Cancel
          </button>
          <button type="submit" disabled={mutation.isPending} className={primaryButtonClasses}>
            {mutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Cloud aria-hidden="true" className="size-4" />
            )}
            Request deployment
          </button>
        </div>
      </form>
    </Modal>
  );
}
