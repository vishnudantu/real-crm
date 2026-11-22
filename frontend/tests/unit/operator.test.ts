import test from "node:test";
import assert from "node:assert/strict";
import {
  featureRecordToRows,
  featureRowsToRecord,
  formatInrFromPaise,
  paiseToRupeesInput,
  rupeesInputToPaise,
} from "../../src/operator/format.ts";
import {
  featureMatrixDiff,
  featureMatrixPayload,
  formatIsoDay,
  healthWorstColor,
  humanizeAction,
  humanizeIdentifier,
  isUuidLike,
  summarizeAuditDetails,
  themeString,
  usageCardData,
  usagePeriodLabel,
} from "../../src/operator/operatorModel.ts";
import type {
  TenantFeatureEntry,
  TenantUsageMeter,
} from "../../src/operator/operatorModel.ts";

test("converts INR rupee inputs to integer paise without floating-point drift", () => {
  assert.equal(rupeesInputToPaise("1499"), 149900);
  assert.equal(rupeesInputToPaise(" 1499.25 "), 149925);
  assert.equal(rupeesInputToPaise("0.01"), 1);
  assert.equal(rupeesInputToPaise("999.999"), Number.NaN);
  assert.equal(rupeesInputToPaise("-10"), Number.NaN);
  assert.equal(rupeesInputToPaise(""), Number.NaN);
  assert.equal(rupeesInputToPaise("1,499"), Number.NaN);
  assert.equal(paiseToRupeesInput(149900), "1499");
  assert.equal(paiseToRupeesInput(149925), "1499.25");
  assert.equal(formatInrFromPaise(149900), "₹1,499");
});

test("maps editable plan feature rows to the backend object and back", () => {
  const features = featureRowsToRecord([
    { key: "ai_assistant", value: "true" },
    { key: "custom_domain", value: "" },
    { key: "", value: "ignored" },
  ]);
  assert.deepEqual(features, {
    ai_assistant: "true",
    custom_domain: true,
  });
  assert.deepEqual(featureRecordToRows(features), [
    { key: "ai_assistant", value: "true" },
    { key: "custom_domain", value: "" },
  ]);
});

function featureRow(overrides: Partial<TenantFeatureEntry>): TenantFeatureEntry {
  return {
    feature: "omnichannel_inbox",
    label: "Omnichannel inbox",
    description: "One inbox",
    enabled: true,
    source: "PLAN",
    reason: null,
    updated_at: null,
    ...overrides,
  };
}

test("featureMatrixDiff stages only rows whose toggle moved", () => {
  const rows = [
    featureRow({ feature: "a_inbox", label: "Inbox", enabled: true }),
    featureRow({ feature: "b_calling", label: "Calling", enabled: false }),
    featureRow({ feature: "c_sla", label: "SLA", enabled: true }),
  ];

  const noChanges = featureMatrixDiff(rows, {});
  assert.deepEqual(noChanges, []);

  const changed = featureMatrixDiff(rows, { b_calling: true, a_inbox: true });
  assert.deepEqual(changed, [
    { feature: "b_calling", label: "Calling", from: false, to: true },
  ]);

  const reverted = featureMatrixDiff(rows, { a_inbox: false, c_sla: false });
  assert.deepEqual(
    reverted.map((change) => change.feature),
    ["a_inbox", "c_sla"],
  );
});

test("featureMatrixPayload converts staged diff into bulk PUT body", () => {
  const payload = featureMatrixPayload([
    { feature: "calling", label: "Calling", from: false, to: true },
    { feature: "sla", label: "SLA", from: true, to: false },
  ]);
  assert.deepEqual(payload, { calling: true, sla: false });
});

test("humanizeAction maps the known action vocabulary and falls back gracefully", () => {
  assert.equal(humanizeAction("TENANT_PROVISIONED"), "Tenant provisioned");
  assert.equal(humanizeAction("TENANT_CONFIG_UPDATED"), "Tenant config updated");
  assert.equal(humanizeAction("FEATURE_ENABLED"), "Feature enabled");
  assert.equal(humanizeAction("FEATURE_DISABLED"), "Feature disabled");
  assert.equal(humanizeAction("IMPERSONATION_STARTED"), "Impersonation started");
  assert.equal(humanizeAction("PLAN_CREATED"), "Plan created");
  assert.equal(humanizeAction("OPERATOR_UPDATED"), "Operator updated");
  assert.equal(humanizeAction("DEPLOYMENT_REQUESTED"), "Deployment requested");
  // Unknown actions fall back to identifier humanization.
  assert.equal(humanizeAction("BRAND_NEW_ACTION"), "Brand New Action");
  assert.equal(humanizeAction("SOME_FEATURE_RESET_X"), "Some Feature Reset X");
});

test("healthWorstColor returns the worst state across mixed health states", () => {
  assert.equal(healthWorstColor([]), "green");
  assert.equal(healthWorstColor(["green", "green"]), "green");
  assert.equal(healthWorstColor(["green", "yellow"]), "yellow");
  assert.equal(healthWorstColor(["yellow", "yellow"]), "yellow");
  assert.equal(healthWorstColor(["green", "yellow", "red"]), "red");
  assert.equal(healthWorstColor(["red"]), "red");
  // Unknown probe states read as yellow (not silently green).
  assert.equal(healthWorstColor(["magenta"]), "yellow");
  assert.equal(healthWorstColor(["green", "magenta"]), "yellow");
});

test("usageCardData orders known meters, computes percent, and tolerates null limits", () => {
  const meters: Record<string, TenantUsageMeter> = {
    users: {
      used: 8,
      limit: 10,
      period_start: null,
      period_end: null,
      period_source: null,
    },
    leads: {
      used: 950,
      limit: 1000,
      period_start: "2026-11-01T00:00:00+00:00",
      period_end: "2026-11-30T23:59:59+00:00",
      period_source: "SUBSCRIPTION",
    },
    messages: {
      used: 40,
      limit: null,
      period_start: "2026-10-23T00:00:00+00:00",
      period_end: "2026-11-22T00:00:00+00:00",
      period_source: "ROLLING_30D",
    },
  };
  const cards = usageCardData(meters);
  assert.deepEqual(
    cards.map((card) => card.key),
    ["leads", "messages", "users"],
  );
  assert.equal(cards[0].percent, 95);
  assert.equal(cards[1].percent, null);
  assert.equal(cards[2].percent, 80);
  assert.equal(cards[0].label, "Leads this period");
  assert.equal(cards[2].label, "Active users");
  // Unknown meter keys are humanized and appended.
  const extra = usageCardData({
    page_views: { used: 5, limit: 100, period_start: null, period_end: null, period_source: null },
  });
  assert.equal(extra.length, 1);
  assert.equal(extra[0].label, "Page Views");
});

test("usagePeriodLabel formats subscription, rolling, and live windows", () => {
  const subscription: TenantUsageMeter = {
    used: 1,
    limit: 10,
    period_start: "2026-11-01T00:00:00+00:00",
    period_end: "2026-11-30T00:00:00+00:00",
    period_source: "SUBSCRIPTION",
  };
  assert.equal(
    usagePeriodLabel(subscription),
    "Subscription period · 1 Nov – 30 Nov",
  );

  const rolling: TenantUsageMeter = {
    used: 1,
    limit: 10,
    period_start: "2026-10-24T00:00:00+00:00",
    period_end: "2026-11-23T00:00:00+00:00",
    period_source: "ROLLING_30D",
  };
  assert.equal(
    usagePeriodLabel(rolling),
    "Rolling 30-day window · 24 Oct – 23 Nov",
  );

  const live: TenantUsageMeter = {
    used: 1,
    limit: null,
    period_start: null,
    period_end: null,
    period_source: null,
  };
  assert.equal(usagePeriodLabel(live), "Live count · no billing period");
});

test("formatIsoDay renders UTC dates without locale drift", () => {
  assert.equal(formatIsoDay("2026-11-01T00:00:00+00:00"), "1 Nov");
  assert.equal(formatIsoDay("2026-11-01"), "1 Nov");
  assert.equal(formatIsoDay(null), "");
});

test("isUuidLike gates Tenant 360 deep links to real UUID resource ids", () => {
  assert.equal(isUuidLike("0f0e9d8c-7b6a-5432-1098-76543210fedc"), true);
  assert.equal(isUuidLike("0F0E9D8C-7B6A-5432-1098-76543210FEDC"), true);
  assert.equal(isUuidLike("acme-realty:calling"), false);
  assert.equal(isUuidLike(null), false);
  assert.equal(isUuidLike(""), false);
});

test("themeString reads single-level theme values and defaults to empty", () => {
  assert.equal(themeString({ primary: "#536B59" }, "primary"), "#536B59");
  assert.equal(themeString({ welcome_message: 42 }, "welcome_message"), "");
  assert.equal(themeString(null, "primary"), "");
  assert.equal(themeString(undefined, "primary"), "");
});

test("summarizeAuditDetails builds human summaries for common payloads", () => {
  assert.equal(
    summarizeAuditDetails({ slug: "acme-realty", changed_fields: {} }),
    "acme-realty",
  );
  assert.equal(
    summarizeAuditDetails({ tenant_slug: "acme", provider: "railway" }),
    "acme",
  );
  assert.equal(
    summarizeAuditDetails({ enabled: true, reason: "Upsell" }),
    "Enabled · Upsell",
  );
  assert.equal(summarizeAuditDetails({ status: "suspended" }), "Suspended");
  assert.equal(
    summarizeAuditDetails({ target_email: "admin@acme.test" }),
    "admin@acme.test",
  );
  assert.equal(summarizeAuditDetails({}), "No change payload");
});

test("humanizeIdentifier converts snake case keys to readable labels", () => {
  assert.equal(humanizeIdentifier("omnichannel_inbox"), "Omnichannel Inbox");
  assert.equal(humanizeIdentifier("TENANT_FEATURE"), "Tenant Feature");
});
