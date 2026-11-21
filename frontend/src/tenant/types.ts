export const TENANT_THEMES = ["light", "dark", "SYSTEM"] as const;

export type TenantTheme = (typeof TENANT_THEMES)[number];

export interface TenantBranding {
  id: string | null;
  slug: string;
  brand_name: string;
  logo_url: string | null;
  primary_color: string;
  theme: TenantTheme;
  default_dark_mode: boolean;
  currency: string;
  timezone: string;
  date_format: string;
}

export type TenantBrandingInput = Omit<TenantBranding, "id" | "slug">;

export type UpdateTenantBrandingPayload = TenantBrandingInput;

export interface TenantContextValue {
  branding: TenantBranding;
  isLoading: boolean;
  isUsingDefaults: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}
