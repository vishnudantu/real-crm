import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, CheckCircle2, Copy, LoaderCircle } from "lucide-react";
import { fetchProjects } from "../admin/api";
import { useFeatures } from "../features/FeaturesProvider";
import { FeatureNotEnabledPage } from "../omnichannel/FeatureNotEnabledPage";
import { errorMessage } from "../shared/apiRequest";
import { fetchMetaPages, finalizeMeta, type MetaFinalizeResult } from "./api";

const STATE_TONE: Record<ProviderCardStateTone, string> = {
  info: "border-charcoal/10 bg-charcoal/5 text-charcoal/60",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  bad: "border-rose-200 bg-rose-50 text-rose-700",
};

type ProviderCardStateTone = "info" | "ok" | "bad";

export function MetaPageSelectStep() {
  const { enabled, isLoading: featuresLoading } = useFeatures();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const ticket = searchParams.get("ticket") ?? "";
  const [pageId, setPageId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MetaFinalizeResult | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: pages, isLoading } = useQuery({
    queryKey: ["connect", "meta-pages", ticket],
    queryFn: () => fetchMetaPages(ticket),
    enabled: ticket.length > 0,
  });
  const { data: projectsData } = useQuery({
    queryKey: ["admin", "projects", "lookup"],
    queryFn: () => fetchProjects({ pageSize: 100 }),
  });
  const projects = projectsData?.items ?? [];

  if (!featuresLoading && !enabled("connectors")) return <FeatureNotEnabledPage />;

  if (!ticket) {
    return (
      <Banner tone="bad" text="No connection ticket found in the URL. Start the Facebook login again from Ad connections." />
    );
  }

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const finalized = await finalizeMeta({
        connection_id: ticket,
        page_id: pageId,
        project_id: projectId,
      });
      setResult(finalized);
      void queryClient.invalidateQueries({ queryKey: ["connect", "connections"] });
      void queryClient.invalidateQueries({ queryKey: ["connect", "providers"] });
    } catch (err) {
      setError(errorMessage(err, "Finishing the Meta connection failed."));
    } finally {
      setSaving(false);
    }
  };

  if (result) {
    const copy = () => {
      try {
        void navigator.clipboard.writeText(result.webhook_url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        setCopied(false);
      }
    };
    return (
      <div className="mx-auto max-w-2xl space-y-5">
        <h1 className="text-xl font-semibold text-charcoal">Meta Lead Ads connected</h1>
        <Banner tone="ok" text={`Page ${result.connection.external_account_id} now routes leads to PropFlow.`} />
        <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
          <h2 className="text-sm font-semibold text-charcoal">Finish these steps in the Meta app dashboard</h2>
          <p className="mt-3 text-xs font-semibold text-charcoal/70">Webhook callback URL</p>
          <div className="mt-1 flex items-center gap-2">
            <code className="flex-1 truncate rounded-lg border border-charcoal/15 bg-charcoal/5 px-3 py-2 font-mono text-xs">
              {result.webhook_url}
            </code>
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1 rounded-lg border border-charcoal/15 px-2.5 py-2 text-xs font-semibold text-charcoal/70 hover:bg-charcoal/5"
            >
              <Copy aria-hidden="true" className="size-3.5" /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="mt-3 text-xs font-semibold text-charcoal/70">
            Verify token — shown once, store it now; PropFlow keeps only its hash
          </p>
          <code className="mt-1 block break-all rounded-lg border border-charcoal/15 bg-charcoal/5 px-3 py-2 font-mono text-xs text-charcoal/80">
            {result.webhook_verify_token}
          </code>
          <ol className="mt-4 space-y-2">
            {result.subscription_checklist.map((step) => (
              <li key={step} className="flex items-start gap-2 text-xs text-charcoal/70">
                <CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                {step}
              </li>
            ))}
          </ol>
        </section>
        <div className="flex gap-4">
          <Link
            to="/admin/integrations"
            className="rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
          >
            Back to Ad connections
          </Link>
          <button
            type="button"
            onClick={() => void navigate("/admin/integrations")}
            className="text-xs font-semibold text-sky-800 hover:underline"
          >
            Test the connection there
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-charcoal/60">
        <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> Loading your Facebook Pages…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-charcoal">Choose the Page that runs Lead Ads</h1>
        <p className="text-sm text-charcoal/60">
          Signed in with Facebook. Pick a Page and the project its leads belong to. This selection
          session expires after 30 minutes.
        </p>
      </header>
      {error && <Banner tone="bad" text={error} />}
      {pages && pages.pages.length > 0 ? (
        <fieldset className="space-y-2">
          <legend className="text-xs font-semibold text-charcoal/70">Facebook Pages you manage</legend>
          {pages.pages.map((page) => (
            <label
              key={page.id}
              className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm transition ${
                pageId === page.id
                  ? "border-sky-500 bg-sky-50/60"
                  : "border-charcoal/10 bg-white hover:border-charcoal/25"
              }`}
            >
              <input
                type="radio"
                name="page"
                value={page.id}
                checked={pageId === page.id}
                onChange={() => setPageId(page.id)}
                className="accent-sky-700"
              />
              <span className="flex-1 font-medium text-charcoal">{page.name}</span>
              <span className="font-mono text-xs text-charcoal/50">{page.id}</span>
            </label>
          ))}
        </fieldset>
      ) : (
        <Banner tone="bad" text="Facebook returned no manageable Pages. Reconnect with an account that administers a Page." />
      )}
      <label className="block text-xs font-semibold text-charcoal/70">
        Route leads to project
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
          disabled={saving || !pageId || !projectId}
          className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
          Connect this Page
        </button>
        <Link to="/admin/integrations" className="text-xs font-semibold text-charcoal/60 hover:underline">
          Cancel
        </Link>
      </div>
    </div>
  );
}

function Banner({ tone, text }: { tone: ProviderCardStateTone; text: string }) {
  return (
    <p
      role={tone === "bad" ? "alert" : undefined}
      className={`flex items-start gap-2 rounded-lg border px-4 py-2 text-sm ${STATE_TONE[tone]}`}
    >
      {tone === "bad" ? (
        <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      ) : (
        <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      )}
      {text}
    </p>
  );
}
