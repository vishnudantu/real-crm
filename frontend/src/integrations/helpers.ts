/**
 * Pure presentation helpers for the guided ad-connection page.
 *
 * Kept free of React and fetch so they are covered by node:test.
 */

export interface ConnectProviderConfig {
  provider: string;
  mode: "oauth" | "manual";
  configured: boolean;
  missing: string[];
  instructions_url: string;
}

export interface ConnectionRow {
  id: string;
  provider: string;
  external_account_id: string;
  project_id: string | null;
  is_active: boolean;
  connection_status: string;
  pending_expires_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export type ProviderCardState =
  | "connected"
  | "attention"
  | "pending"
  | "oauth_ready"
  | "setup_required";

export interface ProviderCardView {
  provider: string;
  label: string;
  state: ProviderCardState;
  stateLabel: string;
  connection: ConnectionRow | null;
  config: ConnectProviderConfig | null;
}

const PROVIDER_LABELS: Record<string, string> = {
  meta_lead_ads: "Meta Lead Ads",
  google_ads: "Google Ads",
};

const STATE_LABELS: Record<ProviderCardState, string> = {
  connected: "Connected",
  attention: "Needs attention",
  pending: "Waiting for selection",
  oauth_ready: "Ready to connect",
  setup_required: "Server setup required",
};

export function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

/**
 * One honest status per provider card. A pending ticket outranks an older
 * active row only when no active row exists for the provider.
 */
export function buildProviderCards(
  providers: readonly ConnectProviderConfig[],
  connections: readonly ConnectionRow[],
): ProviderCardView[] {
  return providers.map((config) => {
    const rows = connections.filter((row) => row.provider === config.provider);
    const active = rows.find((row) => row.connection_status === "ACTIVE" || row.is_active);
    const pending = rows.find((row) => row.connection_status === "PENDING_SELECTION");
    let state: ProviderCardState;
    if (active && !active.is_active) state = "attention";
    else if (active && active.last_error) state = "attention";
    else if (active) state = "connected";
    else if (pending) state = "pending";
    else if (config.configured) state = "oauth_ready";
    else state = "setup_required";
    return {
      provider: config.provider,
      label: providerLabel(config.provider),
      state,
      stateLabel: STATE_LABELS[state],
      connection: active ?? pending ?? null,
      config,
    };
  });
}

export type HealthLabel = "Healthy" | "Failing" | "Never verified" | "Pending";

export function connectionHealthLabel(
  connection: Pick<
    ConnectionRow,
    "is_active" | "connection_status" | "last_success_at" | "last_error"
  >,
): HealthLabel {
  if (connection.connection_status === "PENDING_SELECTION") return "Pending";
  if (!connection.is_active) return "Pending";
  if (connection.last_error) return "Failing";
  if (connection.last_success_at) return "Healthy";
  return "Never verified";
}

/** OAuth starts need a bearer header, so the SPA fetches the URL then navigates. */
export function connectUrlPath(provider: "meta" | "google"): string {
  return `/integrations/connect/${provider}/connect-url`;
}

/** The Meta app dashboard callback URL for leadgen webhooks. */
export function webhookUrl(apiBaseUrl: string): string {
  return `${apiBaseUrl.replace(/\/+$/, "").replace(/\/api\/v1\/?$/, "")}/api/v1/webhooks/meta`;
}

export function selectionPath(ticket: string): string {
  return `ticket=${encodeURIComponent(ticket)}`;
}

export function missingEnvHint(missing: readonly string[]): string {
  if (missing.length === 0) return "";
  return `Set ${missing.join(", ")} in the backend environment and redeploy.`;
}
