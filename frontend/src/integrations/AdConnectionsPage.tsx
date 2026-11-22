import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  LoaderCircle,
  Plug,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useFeatures } from "../features/FeaturesProvider";
import { FeatureNotEnabledPage } from "../omnichannel/FeatureNotEnabledPage";
import { errorMessage } from "../shared/apiRequest";
import {
  fetchConnectProviders,
  fetchConnectUrl,
  fetchConnections,
  revokeConnection,
  testConnection,
} from "./api";
import {
  buildProviderCards,
  connectionHealthLabel,
  missingEnvHint,
  type ConnectionRow,
  type ProviderCardView,
} from "./helpers";

const BACKEND_DOCS: Record<string, string> = {
  meta_lead_ads: "https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow",
  google_ads: "https://developers.google.com/google-ads/api/oauth-explained",
};

function cardAccent(state: ProviderCardView["state"]): string {
  if (state === "connected") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (state === "attention") return "border-rose-200 bg-rose-50 text-rose-700";
  if (state === "pending") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-charcoal/10 bg-charcoal/5 text-charcoal/60";
}

function ProviderCard({ card }: { card: ProviderCardView }) {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const provider = card.provider === "google_ads" ? "google" : "meta";
      const { url } = await fetchConnectUrl(provider);
      // Full-page navigation: Facebook/Google must see a real browser redirect.
      window.location.assign(url);
    } catch (err) {
      setError(errorMessage(err, "Could not start the OAuth connection."));
      setConnecting(false);
    }
  };

  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Plug aria-hidden="true" className="size-5 text-charcoal/70" />
          <h2 className="text-base font-semibold text-charcoal">{card.label}</h2>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[0.68rem] font-semibold ${cardAccent(card.state)}`}>
          {card.stateLabel}
        </span>
      </div>
      <p className="mt-1 text-sm text-charcoal/60">
        {card.provider === "meta_lead_ads"
          ? "Log in with Facebook once, pick your Pages, and PropFlow ingests every lead automatically."
          : "Log in with Google to store offline-conversion credentials for lead and deal reporting."}
      </p>

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </p>
      )}

      {card.state === "setup_required" ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/60 p-4">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
            <ShieldAlert aria-hidden="true" className="size-4" />
            One-click login needs app credentials on this server
          </p>
          <p className="mt-1 text-xs text-amber-800/90">
            {missingEnvHint(card.config?.missing ?? [])}
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-charcoal/70">
            {(card.config?.missing ?? []).map((name) => (
              <li key={name}>
                <code className="rounded bg-charcoal/5 px-1 font-mono text-[0.7rem]">{name}</code> is not set
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-3">
            <a
              href={card.config?.instructions_url ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-sky-800 hover:underline"
            >
              {card.config?.instructions_url ?? "#"} <ExternalLink aria-hidden="true" className="size-3" />
            </a>
            <a
              href={BACKEND_DOCS[card.provider]}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-sky-800 hover:underline"
            >
              OAuth docs <ExternalLink aria-hidden="true" className="size-3" />
            </a>
          </div>
          {card.provider === "google_ads" && (
            <Link
              to="/admin/integrations/google/select"
              className="mt-2 inline-block text-xs font-semibold text-sky-800 hover:underline"
            >
              Have the credentials already? Enter them manually
            </Link>
          )}
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-3">
          {card.provider === "meta_lead_ads" ? (
            card.state === "pending" && card.connection ? (
              <Link
                to={`/admin/integrations/meta/select?ticket=${encodeURIComponent(card.connection.id)}`}
                className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
              >
                Finish connecting — choose a Page
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => void connect()}
                disabled={connecting}
                className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90 disabled:opacity-50"
              >
                {connecting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
                {card.state === "connected" ? "Reconnect with Facebook" : "Connect with Facebook"}
              </button>
            )
          ) : card.state === "pending" && card.connection ? (
            <Link
              to={`/admin/integrations/google/select?ticket=${encodeURIComponent(card.connection.id)}`}
              className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
            >
              Finish connecting — enter customer ID
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => void connect()}
              disabled={connecting}
              className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90 disabled:opacity-50"
            >
              {connecting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
              {card.state === "connected" ? "Reconnect with Google" : "Connect with Google"}
            </button>
          )}
          {card.state === "connected" && card.connection && (
            <button
              type="button"
              onClick={() =>
                void queryClient.invalidateQueries({ queryKey: ["connect", "providers"] })
              }
              className="text-xs font-semibold text-charcoal/60 hover:underline"
            >
              Refresh status
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function ConnectionsTable() {
  const queryClient = useQueryClient();
  const [testing, setTesting] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: connections, isLoading } = useQuery({
    queryKey: ["connect", "connections"],
    queryFn: fetchConnections,
  });

  const runTest = async (row: ConnectionRow) => {
    setTesting(row.id);
    setMessage(null);
    setError(null);
    try {
      const provider = row.provider === "google_ads" ? "google" : "meta";
      const result = await testConnection(provider, row.id);
      setMessage(result.message);
    } catch (err) {
      setError(errorMessage(err, "The provider test failed."));
    } finally {
      setTesting(null);
      void queryClient.invalidateQueries({ queryKey: ["connect", "connections"] });
    }
  };

  const revoke = async (connectionId: string) => {
    setError(null);
    try {
      await revokeConnection(connectionId);
      setMessage("Connection revoked and credentials deleted.");
    } catch (err) {
      setError(errorMessage(err, "Revoking the connection failed."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: ["connect", "connections"] });
      void queryClient.invalidateQueries({ queryKey: ["connect", "providers"] });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-charcoal/60">
        <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> Loading connections…
      </div>
    );
  }
  const rows = (connections ?? []).filter((row) => row.connection_status !== "PENDING_SELECTION");
  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
      <h2 className="text-base font-semibold text-charcoal">Connected accounts</h2>
      {message && (
        <p className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-charcoal/60">Nothing connected yet.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="text-charcoal/50">
              <tr>
                <th className="py-2 pr-3 font-semibold">Provider</th>
                <th className="py-2 pr-3 font-semibold">Account</th>
                <th className="py-2 pr-3 font-semibold">Health</th>
                <th className="py-2 pr-3 font-semibold">Last success</th>
                <th className="py-2 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const label = connectionHealthLabel(row);
                const tone =
                  label === "Healthy"
                    ? "text-emerald-700"
                    : label === "Failing"
                      ? "text-rose-700"
                      : "text-charcoal/60";
                return (
                  <tr key={row.id} className="border-t border-charcoal/5">
                    <td className="py-2 pr-3 font-medium text-charcoal">
                      {row.provider === "google_ads" ? "Google Ads" : "Meta Lead Ads"}
                    </td>
                    <td className="py-2 pr-3 font-mono">{row.external_account_id}</td>
                    <td className={`py-2 pr-3 font-semibold ${tone}`}>{label}</td>
                    <td className="py-2 pr-3 text-charcoal/60">
                      {row.last_success_at ? new Date(row.last_success_at).toLocaleString() : "—"}
                    </td>
                    <td className="py-2">
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => void runTest(row)}
                          disabled={testing === row.id}
                          className="inline-flex items-center gap-1 font-semibold text-sky-800 hover:underline disabled:opacity-50"
                        >
                          {testing === row.id ? (
                            <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
                          ) : (
                            <RefreshCw aria-hidden="true" className="size-3" />
                          )}
                          Test
                        </button>
                        <button
                          type="button"
                          onClick={() => void revoke(row.id)}
                          className="inline-flex items-center gap-1 font-semibold text-rose-700 hover:underline"
                        >
                          <Trash2 aria-hidden="true" className="size-3" /> Revoke
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function AdConnectionsPage() {
  const { enabled, isLoading: featuresLoading } = useFeatures();
  const [searchParams] = useSearchParams();
  const callbackError = searchParams.get("error");
  const { data: providers, isLoading } = useQuery({
    queryKey: ["connect", "providers"],
    queryFn: fetchConnectProviders,
  });
  const { data: connections } = useQuery({
    queryKey: ["connect", "connections"],
    queryFn: fetchConnections,
  });

  if (!featuresLoading && !enabled("connectors")) return <FeatureNotEnabledPage />;

  const cards = providers ? buildProviderCards(providers, connections ?? []) : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-charcoal">Ad connections</h1>
        <p className="text-sm text-charcoal/60">
          Connect Meta Lead Ads and Google Ads with one login. Credentials are encrypted per
          organization and never shown again after saving.
        </p>
      </header>

      {callbackError && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700"
        >
          <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {callbackError}
        </p>
      )}

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-charcoal/60">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> Checking provider setup…
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {cards.map((card) => (
            <ProviderCard key={card.provider} card={card} />
          ))}
        </div>
      )}

      <ConnectionsTable />

      <p className="flex items-center gap-1.5 text-[0.7rem] text-charcoal/50">
        <CheckCircle2 aria-hidden="true" className="size-3" />
        PropFlow only calls Meta or Google when you click Connect or Test — no background polling.
      </p>
    </div>
  );
}
