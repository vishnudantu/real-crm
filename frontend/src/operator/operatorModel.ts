export type OperatorRole = "OWNER" | "SUPPORT" | "SALES" | "DEPLOYER";

export type OperatorPermission =
  | "tenants.read"
  | "tenants.write"
  | "plans.write"
  | "deployments.write"
  | "operators.manage"
  | "audit.read";

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
