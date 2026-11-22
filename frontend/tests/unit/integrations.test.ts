import test from "node:test";
import assert from "node:assert/strict";
import {
  buildProviderCards,
  connectionHealthLabel,
  connectUrlPath,
  missingEnvHint,
  webhookUrl,
  type ConnectProviderConfig,
  type ConnectionRow,
} from "../../src/integrations/helpers.ts";

function config(
  provider: string,
  overrides: Partial<ConnectProviderConfig> = {},
): ConnectProviderConfig {
  return {
    provider,
    mode: "oauth",
    configured: true,
    missing: [],
    instructions_url: "https://developers.facebook.com/apps/",
    ...overrides,
  };
}

function row(overrides: Partial<ConnectionRow> = {}): ConnectionRow {
  return {
    id: "conn-1",
    provider: "meta_lead_ads",
    external_account_id: "page-77",
    project_id: "proj-1",
    is_active: true,
    connection_status: "ACTIVE",
    pending_expires_at: null,
    last_success_at: null,
    last_error: null,
    created_at: "2026-11-22T00:00:00Z",
    updated_at: "2026-11-22T00:00:00Z",
    ...overrides,
  };
}

test("provider card reports connected when an active row exists", () => {
  const cards = buildProviderCards(
    [config("meta_lead_ads"), config("google_ads")],
    [row()],
  );
  const meta = cards.find((card) => card.provider === "meta_lead_ads");
  assert.equal(meta?.state, "connected");
  assert.equal(meta?.stateLabel, "Connected");
  assert.equal(meta?.connection?.id, "conn-1");
  assert.equal(cards.find((card) => card.provider === "google_ads")?.state, "oauth_ready");
});

test("provider card flags attention on errors or inactive rows", () => {
  const failing = buildProviderCards([config("meta_lead_ads")], [row({ last_error: "token expired" })]);
  assert.equal(failing[0].state, "attention");
  const inactive = buildProviderCards(
    [config("meta_lead_ads")],
    [row({ is_active: false, connection_status: "ACTIVE" })],
  );
  assert.equal(inactive[0].state, "attention");
});

test("a pending selection outranks no connection but never an active one", () => {
  const pendingOnly = buildProviderCards(
    [config("google_ads")],
    [row({ provider: "google_ads", connection_status: "PENDING_SELECTION", is_active: false })],
  );
  assert.equal(pendingOnly[0].state, "pending");
  const activeAndPending = buildProviderCards(
    [config("meta_lead_ads")],
    [
      row(),
      row({ id: "conn-2", connection_status: "PENDING_SELECTION", is_active: false, external_account_id: "page-78" }),
    ],
  );
  assert.equal(activeAndPending[0].state, "connected");
});

test("oauth ready only when the provider is configured server-side", () => {
  const cards = buildProviderCards([config("meta_lead_ads", { configured: false, mode: "manual", missing: ["META_OAUTH_CLIENT_ID"] })], []);
  assert.equal(cards[0].state, "setup_required");
  const ready = buildProviderCards([config("meta_lead_ads")], []);
  assert.equal(ready[0].state, "oauth_ready");
});

test("health labels map exactly to stored connection state", () => {
  assert.equal(connectionHealthLabel(row({ last_success_at: "2026-11-22T10:00:00Z" })), "Healthy");
  assert.equal(connectionHealthLabel(row({ last_error: "boom" })), "Failing");
  assert.equal(connectionHealthLabel(row()), "Never verified");
  assert.equal(connectionHealthLabel(row({ connection_status: "PENDING_SELECTION" })), "Pending");
  assert.equal(connectionHealthLabel(row({ is_active: false })), "Pending");
});

test("webhook url builder normalizes api base URLs to the backend webhook", () => {
  assert.equal(webhookUrl("http://127.0.0.1:8000/api/v1"), "http://127.0.0.1:8000/api/v1/webhooks/meta");
  assert.equal(webhookUrl("https://api.propflow.test/api/v1/"), "https://api.propflow.test/api/v1/webhooks/meta");
  assert.equal(webhookUrl("https://api.propflow.test"), "https://api.propflow.test/api/v1/webhooks/meta");
});

test("connect url paths match the backend authed start endpoints", () => {
  assert.equal(connectUrlPath("meta"), "/integrations/connect/meta/connect-url");
  assert.equal(connectUrlPath("google"), "/integrations/connect/google/connect-url");
});

test("missing env hint names the variables without inventing an action", () => {
  assert.equal(missingEnvHint([]), "");
  assert.match(missingEnvHint(["GOOGLE_ADS_DEVELOPER_TOKEN"]), /GOOGLE_ADS_DEVELOPER_TOKEN/);
});
