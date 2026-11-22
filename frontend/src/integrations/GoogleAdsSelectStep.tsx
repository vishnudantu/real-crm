import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, LoaderCircle } from "lucide-react";
import { fetchProjects } from "../admin/api";
import { useFeatures } from "../features/FeaturesProvider";
import { FeatureNotEnabledPage } from "../omnichannel/FeatureNotEnabledPage";
import { errorMessage } from "../shared/apiRequest";
import { connectGoogleManually, finalizeGoogle, type GoogleManualPayload } from "./api";

const CUSTOMER_ID_PATTERN = /^\d{10}$/;

const EMPTY_MANUAL: GoogleManualPayload = {
  developer_token: "",
  refresh_token: "",
  client_id: "",
  client_secret: "",
  customer_id: "",
  project_id: "",
};

export function GoogleAdsSelectStep() {
  const { enabled, isLoading: featuresLoading } = useFeatures();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const ticket = searchParams.get("ticket") ?? "";
  const [customerId, setCustomerId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const { data: projectsData } = useQuery({
    queryKey: ["admin", "projects", "lookup"],
    queryFn: () => fetchProjects({ pageSize: 100 }),
  });
  const projects = projectsData?.items ?? [];

  if (!featuresLoading && !enabled("connectors")) return <FeatureNotEnabledPage />;

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await finalizeGoogle({
        connection_id: ticket,
        customer_id: customerId,
        project_id: projectId,
      });
      setDone(true);
      void queryClient.invalidateQueries({ queryKey: ["connect", "connections"] });
      void queryClient.invalidateQueries({ queryKey: ["connect", "providers"] });
    } catch (err) {
      setError(errorMessage(err, "Finishing the Google Ads connection failed."));
    } finally {
      setSaving(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold text-charcoal">Google Ads connected</h1>
        <p className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          <CheckCircle2 aria-hidden="true" className="size-4" />
          Customer {customerId} is mapped to the selected project. Run Test from Ad connections to
          verify the developer token and refresh token.
        </p>
        <Link
          to="/admin/integrations"
          className="inline-block rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
        >
          Back to Ad connections
        </Link>
      </div>
    );
  }

  if (!ticket) return <ManualGoogleForm projects={projects} />;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-charcoal">Finish the Google Ads connection</h1>
        <p className="text-sm text-charcoal/60">
          Signed in with Google. Enter your 10-digit Google Ads customer ID (without hyphens) from
          the top-right account switcher, and the project conversions should map to.
        </p>
      </header>
      {error && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}
      <label className="block text-xs font-semibold text-charcoal/70">
        Customer ID
        <input
          value={customerId}
          onChange={(event) => setCustomerId(event.target.value.replace(/[^\d]/g, "").slice(0, 10))}
          placeholder="1234567890"
          inputMode="numeric"
          autoComplete="off"
          className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 font-mono text-sm font-normal"
        />
      </label>
      <label className="block text-xs font-semibold text-charcoal/70">
        Map conversions to project
        <select
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
        >
          <option value="">Choose a project…</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={saving || !CUSTOMER_ID_PATTERN.test(customerId) || !projectId}
          className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
          Save connection
        </button>
        <Link to="/admin/integrations" className="text-xs font-semibold text-charcoal/60 hover:underline">
          Cancel
        </Link>
      </div>
    </div>
  );
}

function ManualGoogleForm({
  projects,
}: {
  projects: { id: string; name: string }[];
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<GoogleManualPayload>(EMPTY_MANUAL);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const update = (key: keyof GoogleManualPayload, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await connectGoogleManually(form);
      setDone(true);
      void queryClient.invalidateQueries({ queryKey: ["connect", "connections"] });
      void queryClient.invalidateQueries({ queryKey: ["connect", "providers"] });
    } catch (err) {
      setError(errorMessage(err, "Saving the Google Ads credentials failed."));
    } finally {
      setSaving(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold text-charcoal">Google Ads connected</h1>
        <p className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          <CheckCircle2 aria-hidden="true" className="size-4" />
          Credentials stored encrypted. Run Test from Ad connections to verify them with Google.
        </p>
        <Link
          to="/admin/integrations"
          className="inline-block rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
        >
          Back to Ad connections
        </Link>
      </div>
    );
  }

  const fields: { key: keyof GoogleManualPayload; label: string; secret?: boolean }[] = [
    { key: "developer_token", label: "Google Ads developer token" },
    { key: "client_id", label: "OAuth client ID" },
    { key: "client_secret", label: "OAuth client secret", secret: true },
    { key: "refresh_token", label: "Refresh token (offline access)", secret: true },
    {
      key: "customer_id",
      label: "Customer ID (10 digits, no hyphens)",
    },
  ];
  const complete =
    fields.every((field) => form[field.key].trim()) &&
    CUSTOMER_ID_PATTERN.test(form.customer_id) &&
    form.project_id;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-charcoal">Google Ads — manual credentials</h1>
        <p className="text-sm text-charcoal/60">
          Use this when the OAuth app is not configured server-side yet. Values are encrypted per
          organization and never returned after saving.
        </p>
      </header>
      {error && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <label key={field.key} className="text-xs font-semibold text-charcoal/70">
            {field.label}
            <input
              type={field.secret ? "password" : "text"}
              value={form[field.key]}
              autoComplete="off"
              onChange={(event) => update(field.key, event.target.value)}
              className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
            />
          </label>
        ))}
        <label className="text-xs font-semibold text-charcoal/70 sm:col-span-2">
          Map conversions to project
          <select
            value={form.project_id}
            onChange={(event) => update("project_id", event.target.value)}
            className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
          >
            <option value="">Choose a project…</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={saving || !complete}
          className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
          Save credentials
        </button>
        <Link to="/admin/integrations" className="text-xs font-semibold text-charcoal/60 hover:underline">
          Back
        </Link>
      </div>
    </div>
  );
}
