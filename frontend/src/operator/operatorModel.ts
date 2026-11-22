export type OperatorRole = "OWNER" | "SUPPORT" | "SALES" | "DEPLOYER";

export type OperatorPermission =
  | "tenants.read"
  | "tenants.write"
  | "plans.write"
  | "deployments.write"
  | "operators.manage"
  | "audit.read"
  | "tenants.impersonate";

export interface OperatorUser {
  id: string;
  email: string;
  full_name: string;
  role: OperatorRole;
  permissions: OperatorPermission[];
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface OperatorTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export type TenantStatus = "active" | "suspended";

export interface OperatorTenant {
  id: string;
  slug: string;
  name: string;
  brand_name: string;
  status: TenantStatus;
  plan_id: string | null;
  country: string;
  timezone: string;
  currency: string;
  users: number;
  leads: number;
  bookings: number;
  deliveries: number;
}

export interface OperatorTenantDetail extends OperatorTenant {
  theme_json: Record<string, unknown> | null;
}

export interface ProvisionTenantPayload {
  slug: string;
  name: string;
  brand_name?: string;
  admin_email: string;
  admin_full_name: string;
  admin_password: string;
  country: string;
  timezone: string;
  currency: string;
  plan_id?: string;
}

export interface ProvisionTenantResponse {
  id: string;
  slug: string;
  name: string;
  brand_name: string;
  status: TenantStatus;
  plan_id: string | null;
  admin_user_id: string;
  admin_email: string;
}

export interface OnboardTenantPayload {
  slug: string;
  name: string;
  brand_name?: string;
  admin_email: string;
  admin_full_name: string;
  admin_password: string;
  country: string;
  timezone: string;
  currency: string;
  plan_code?: string;
  enable_omnichannel: boolean;
  enable_calling: boolean;
  enable_connectors: boolean;
  enable_post_sales: boolean;
  embed_url?: string;
}

export interface OnboardTenantResponse {
  tenant_id: string;
  slug: string;
  brand_name: string;
  status: TenantStatus;
  plan_id: string | null;
  admin_email: string;
  embed_script_url: string | null;
  enabled_features: string[];
}

export interface OperatorPlan {
  id: string;
  code: string;
  name: string;
  description: string | null;
  price_paise: number;
  currency: string;
  max_users: number;
  leads_per_month: number;
  whatsapp_msgs_per_month: number;
  features: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlanFeatureInput {
  key: string;
  value: string;
}

export interface PlanFormValues {
  code: string;
  name: string;
  description: string;
  priceRupees: string;
  maxUsers: number;
  leadsPerMonth: number;
  whatsappMsgsPerMonth: number;
  featureRows: PlanFeatureInput[];
  isActive: boolean;
}

export interface CreatePlanPayload {
  code: string;
  name: string;
  description?: string | null;
  price_paise: number;
  currency: string;
  max_users: number;
  leads_per_month: number;
  whatsapp_msgs_per_month: number;
  features: Record<string, unknown>;
  is_active: boolean;
}

export interface UpdatePlanPayload {
  name?: string;
  description?: string | null;
  price_paise?: number;
  max_users?: number;
  leads_per_month?: number;
  whatsapp_msgs_per_month?: number;
  features?: Record<string, unknown>;
  is_active?: boolean;
}

export interface CreateOperatorPayload {
  email: string;
  full_name: string;
  password: string;
  role: OperatorRole;
  permissions: string[];
}

export interface UpdateOperatorPayload {
  role?: OperatorRole;
  permissions?: string[];
  is_active?: boolean;
}

export type DeploymentProvider = "railway" | "render" | "aws" | "local" | "manual";

export interface TenantDeploymentPayload {
  provider: DeploymentProvider;
  environment: string;
  region?: string;
  repository_url?: string;
  api_base_url?: string;
  notes?: string;
}

export interface TenantDeploymentResponse {
  id: string;
  tenant_id: string;
  provider: string;
  environment: string;
  region: string | null;
  status: string;
  deployment_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface OperatorAuditLog {
  id: string;
  operator_id: string | null;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogFilters {
  action?: string;
  resource_type?: string;
  actor_email?: string;
  tenant_slug?: string;
  limit?: number;
}

// ---------------------------------------------------------------------------
// Feature catalog and per-tenant entitlement matrix
// ---------------------------------------------------------------------------

export interface FeatureCatalogEntry {
  feature: string;
  label: string;
  description: string;
  default_enabled: boolean;
}

export const FEATURE_SOURCE_OVERRIDE = "TENANT_OVERRIDE";
export const FEATURE_SOURCE_PLAN = "PLAN";
export const FEATURE_SOURCE_CATALOG_DEFAULT = "CATALOG_DEFAULT";

export interface TenantFeatureEntry {
  feature: string;
  label: string;
  description: string;
  enabled: boolean;
  source: string;
  reason: string | null;
  updated_at: string | null;
}

export interface FeatureMatrixChange {
  feature: string;
  label: string;
  from: boolean;
  to: boolean;
}

/** Staged entitlements that differ from the effective server state. */
export function featureMatrixDiff(
  rows: readonly TenantFeatureEntry[],
  staged: Readonly<Record<string, boolean>>,
): FeatureMatrixChange[] {
  const changes: FeatureMatrixChange[] = [];
  for (const row of rows) {
    const next = staged[row.feature];
    if (typeof next === "boolean" && next !== row.enabled) {
      changes.push({ feature: row.feature, label: row.label, from: row.enabled, to: next });
    }
  }
  return changes;
}

/** Convert a staged diff into the bulk PUT payload. */
export function featureMatrixPayload(
  changes: readonly FeatureMatrixChange[],
): Record<string, boolean> {
  return changes.reduce<Record<string, boolean>>(
    (payload, change) => ({ ...payload, [change.feature]: change.to }),
    {},
  );
}

// ---------------------------------------------------------------------------
// Tenant config (control plane)
// ---------------------------------------------------------------------------

export interface TenantPlanSummary {
  id: string;
  code: string;
  name: string;
  price_paise: number;
}

export interface TenantBrandingSummary {
  brand_name: string;
  logo_path: string | null;
  theme_json: Record<string, unknown> | null;
}

export interface TenantWidgetSummary {
  enabled: boolean;
  embed_url: string | null;
}

export interface TenantChannelSummary {
  channel: string;
  provider: string;
  is_active: boolean;
  updated_at: string | null;
}

export interface TenantAISummary {
  provider: string | null;
  model: string | null;
  configured: boolean;
}

export interface TenantFeatureMatrixSummary {
  enabled_count: number;
  total_count: number;
}

export interface TenantCountsSummary {
  users: number;
  active_users: number;
  leads_total: number;
  projects: number;
  bookings: number;
  open_conversations: number;
}

export interface TenantConfig {
  id: string;
  slug: string;
  name: string;
  status: string;
  country: string;
  timezone: string;
  currency: string;
  plan: TenantPlanSummary | null;
  branding: TenantBrandingSummary;
  widget: TenantWidgetSummary;
  channels: TenantChannelSummary[];
  ai: TenantAISummary;
  features: TenantFeatureMatrixSummary;
  counts: TenantCountsSummary;
}

export interface TenantConfigPatchPayload {
  brand_name?: string;
  timezone?: string;
  currency?: string;
  country?: string;
  theme_json?: Record<string, unknown>;
}

/** Read a single-level string from a theme blob without assuming its shape. */
export function themeString(
  themeJson: Record<string, unknown> | null | undefined,
  key: string,
): string {
  const value = themeJson?.[key];
  return typeof value === "string" ? value : "";
}

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface TenantUsageMeter {
  used: number;
  limit: number | null;
  period_start: string | null;
  period_end: string | null;
  period_source: string | null;
}

export interface TenantUsageDailyPoint {
  date: string;
  leads: number;
  messages_sent: number;
}

export interface TenantUsage {
  days: number;
  meters: Record<string, TenantUsageMeter>;
  leads_total: number;
  bookings_total: number;
  messages_sent_total: number;
  active_users: number;
  channels_active: number;
  series: TenantUsageDailyPoint[];
}

export interface UsageCardDatum {
  key: string;
  label: string;
  used: number;
  limit: number | null;
  percent: number | null;
  meter: TenantUsageMeter;
}

const USAGE_METER_LABELS: Record<string, string> = {
  leads: "Leads this period",
  messages: "WhatsApp messages this period",
  users: "Active users",
};

const USAGE_METER_ORDER = ["leads", "messages", "users"];

export function usageCardData(
  meters: Readonly<Record<string, TenantUsageMeter>>,
): UsageCardDatum[] {
  const known = USAGE_METER_ORDER.filter((key) => meters[key] !== undefined);
  const rest = Object.keys(meters)
    .filter((key) => !USAGE_METER_ORDER.includes(key))
    .sort();
  return [...known, ...rest].map((key) => {
    const meter = meters[key];
    const percent =
      typeof meter.limit === "number" && meter.limit > 0
        ? Math.min(100, Math.round((meter.used / meter.limit) * 100))
        : null;
    return {
      key,
      label: USAGE_METER_LABELS[key] ?? humanizeIdentifier(key),
      used: meter.used,
      limit: meter.limit,
      percent,
      meter,
    };
  });
}

export function formatIsoDay(value: string | null): string {
  if (!value) return "";
  const day = value.slice(0, 10);
  const parsed = Date.parse(`${day}T00:00:00Z`);
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(parsed));
}

export function usagePeriodLabel(meter: TenantUsageMeter): string {
  if (meter.period_source === "SUBSCRIPTION") {
    return `Subscription period · ${formatIsoDay(meter.period_start)} – ${formatIsoDay(meter.period_end)}`;
  }
  if (meter.period_source === "ROLLING_30D") {
    return `Rolling 30-day window · ${formatIsoDay(meter.period_start)} – ${formatIsoDay(meter.period_end)}`;
  }
  if (meter.period_source) {
    return `${humanizeIdentifier(meter.period_source)} · ${formatIsoDay(meter.period_start)} – ${formatIsoDay(meter.period_end)}`;
  }
  return "Live count · no billing period";
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export type HealthState = "green" | "yellow" | "red";

export interface TenantHealthCheck {
  name: string;
  state: string;
  detail: string;
}

export interface TenantHealth {
  tenant_id: string;
  overall: string;
  checks: TenantHealthCheck[];
}

/** Worst-case colour across a set of health states; unknowns read as yellow. */
export function healthWorstColor(states: readonly string[]): HealthState {
  let worst = 0;
  for (const state of states) {
    const rank = state === "red" ? 2 : state === "green" ? 0 : 1;
    if (rank > worst) worst = rank;
  }
  return worst === 2 ? "red" : worst === 1 ? "yellow" : "green";
}

// ---------------------------------------------------------------------------
// Impersonation
// ---------------------------------------------------------------------------

export interface ImpersonatedUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface ImpersonationResult {
  access_token: string;
  expires_in: number;
  user: ImpersonatedUser;
}

// ---------------------------------------------------------------------------
// Audit action vocabulary (server-side strings; UI never invents actions)
// ---------------------------------------------------------------------------

export const AUDIT_ACTION_OPTIONS: readonly string[] = [
  "TENANT_PROVISIONED",
  "TENANT_STATUS_CHANGED",
  "TENANT_CONFIG_UPDATED",
  "FEATURE_ENABLED",
  "FEATURE_DISABLED",
  "FEATURE_RESET",
  "PLAN_CREATED",
  "PLAN_UPDATED",
  "OPERATOR_CREATED",
  "OPERATOR_UPDATED",
  "DEPLOYMENT_REQUESTED",
  "IMPERSONATION_STARTED",
];

export const AUDIT_RESOURCE_TYPE_OPTIONS: readonly string[] = [
  "TENANT",
  "TENANT_FEATURE",
  "PLAN",
  "OPERATOR",
  "DEPLOYMENT",
];

const AUDIT_ACTION_LABELS: Record<string, string> = {
  TENANT_PROVISIONED: "Tenant provisioned",
  TENANT_STATUS_CHANGED: "Tenant status changed",
  TENANT_CONFIG_UPDATED: "Tenant config updated",
  FEATURE_ENABLED: "Feature enabled",
  FEATURE_DISABLED: "Feature disabled",
  FEATURE_RESET: "Feature reset",
  PLAN_CREATED: "Plan created",
  PLAN_UPDATED: "Plan updated",
  OPERATOR_CREATED: "Operator created",
  OPERATOR_UPDATED: "Operator updated",
  DEPLOYMENT_REQUESTED: "Deployment requested",
  IMPERSONATION_STARTED: "Impersonation started",
};

export function humanizeIdentifier(value: string): string {
  return value
    .replace(/[._-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function humanizeAction(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? humanizeIdentifier(action);
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuidLike(value: string | null | undefined): boolean {
  return Boolean(value && UUID_PATTERN.test(value));
}

/** Short human summary for an audit row's details payload. */
export function summarizeAuditDetails(details: Record<string, unknown>): string {
  const slug = typeof details.slug === "string" ? details.slug : null;
  const tenantSlug =
    typeof details.tenant_slug === "string" ? details.tenant_slug : null;
  const status = typeof details.status === "string" ? details.status : null;
  const code = typeof details.code === "string" ? details.code : null;
  const feature = typeof details.feature === "string" ? details.feature : null;
  const email =
    typeof details.target_email === "string" ? details.target_email : null;
  const reason = typeof details.reason === "string" ? details.reason : null;
  const enabled = typeof details.enabled === "boolean" ? details.enabled : null;
  const parts: string[] = [];
  if (slug) parts.push(slug);
  else if (tenantSlug) parts.push(tenantSlug);
  if (feature) parts.push(humanizeIdentifier(feature));
  if (code) parts.push(code);
  if (status) parts.push(humanizeIdentifier(status));
  if (email) parts.push(email);
  if (enabled !== null && reason) parts.push(`${enabled ? "Enabled" : "Disabled"} · ${reason}`);
  else if (reason) parts.push(reason);
  else if (enabled !== null) parts.push(enabled ? "Enabled" : "Disabled");
  if (parts.length === 0) {
    const keys = Object.keys(details);
    if (keys.length === 0) return "No change payload";
    return keys.slice(0, 3).map(humanizeIdentifier).join(" · ");
  }
  return parts.join(" · ");
}
