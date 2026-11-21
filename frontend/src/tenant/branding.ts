import { z } from "zod";
import type {
  TenantBranding,
  TenantBrandingInput,
} from "./types";

export const DEFAULT_TENANT_SLUG = "default";

export const DEFAULT_BRANDING: Readonly<TenantBranding> = Object.freeze({
  id: null,
  slug: DEFAULT_TENANT_SLUG,
  brand_name: "PropFlow",
  logo_url: null,
  primary_color: "#536B59",
  theme: "light",
  default_dark_mode: false,
  currency: "INR",
  timezone: "Asia/Kolkata",
  date_format: "dd MMM yyyy",
});

const TENANT_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const CURRENCY_PATTERN = /^[A-Z]{3}$/;
const DATE_FORMAT_PATTERN = /^[dDMyY,./\- ]{4,24}$/;

export function normalizeTenantSlug(value: unknown): string {
  const slug = typeof value === "string" ? value.trim().toLowerCase() : "";
  return TENANT_SLUG_PATTERN.test(slug) ? slug : DEFAULT_TENANT_SLUG;
}

/**
 * VITE_TENANT_SLUG is the deployment-time/default route-to-tenant mapping.
 * For production host/path mappings, have the host configuration inject the
 * same value. Browser storage is deliberately not consulted: tenant selection
 * here is for display only, never authorization or cross-tenant object access.
 */
export function resolveTenantSlug(configuredSlug?: string): string {
  return normalizeTenantSlug(configuredSlug ?? import.meta.env.VITE_TENANT_SLUG);
}

const brandingFieldsSchema = z.object({
    id: z.string().min(1).max(100).nullish(),
    slug: z.string().trim().min(1).max(100).regex(TENANT_SLUG_PATTERN).optional(),
    brand_name: z.string().trim().min(1).max(100).optional(),
    logo_url: z.string().trim().max(2048).nullish(),
    primary_color: z
      .string()
      .regex(/^#[\dA-Fa-f]{6}$/)
      .optional(),
    theme: z.union([
      z.enum(["light", "dark", "SYSTEM"]),
      z.record(z.string(), z.unknown()),
    ]).optional(),
    default_dark_mode: z.boolean().optional(),
    currency: z.string().trim().regex(CURRENCY_PATTERN).optional(),
    timezone: z.string().trim().min(1).max(100).optional(),
    date_format: z.string().trim().regex(DATE_FORMAT_PATTERN).optional(),
});

const brandingResponseSchema = brandingFieldsSchema.extend({
  tenant_id: z.string().min(1).max(100).nullish(),
  settings: brandingFieldsSchema.partial().nullable().optional(),
  branding: brandingFieldsSchema.partial().nullable().optional(),
}).passthrough();

function isTimezone(value: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

function isLogoUrl(value: string): boolean {
  if (value.startsWith("/") && !value.startsWith("//") && !value.includes("..")) {
    return true;
  }

  try {
    const url = new URL(value);
    return (
      (url.protocol === "https:" ||
        (url.protocol === "http:" &&
          (url.hostname === "localhost" || url.hostname === "127.0.0.1"))) &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}

function isTheme(value: unknown): value is TenantBranding["theme"] {
  return value === "light" || value === "dark" || value === "SYSTEM";
}

function colorChannels(hex: string): [number, number, number] {
  return [
    Number.parseInt(hex.slice(1, 3), 16),
    Number.parseInt(hex.slice(3, 5), 16),
    Number.parseInt(hex.slice(5, 7), 16),
  ];
}

export function contrastRatio(first: string, second: string): number {
  const luminance = (color: string): number => {
    const channels = colorChannels(color).map((channel) => {
      const value = channel / 255;
      return value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4;
    });
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  };
  const lighter = Math.max(luminance(first), luminance(second));
  const darker = Math.min(luminance(first), luminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

export function accessiblePrimaryColor(value: string): string {
  let color = value.toUpperCase();
  const background = "#F5F2EB";

  while (contrastRatio(color, background) < 4.5) {
    const [red, green, blue] = colorChannels(color).map(Math.round);
    if (red === 0 && green === 0 && blue === 0) return "#000000";
    const adjusted = [red, green, blue].map((channel) =>
      Math.max(0, Math.floor(channel * 0.88)),
    );
    color = `#${adjusted.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
  }

  return color;
}

export function normalizeBranding(
  input: unknown,
  fallback: TenantBranding = { ...DEFAULT_BRANDING },
  requestedSlug: string = fallback.slug,
): TenantBranding {
  const result = brandingResponseSchema.safeParse(input);
  if (!result.success) return { ...fallback };

  const data = result.data;
  const nested = data.branding ?? data.settings;
  const themeObject = typeof data.theme === "object" && data.theme !== null
    ? data.theme as Record<string, unknown>
    : null;
  const merged = { ...nested, ...themeObject, ...data };
  const value = (key: keyof TenantBrandingInput): unknown => merged[key];

  const primary = value("primary_color") ?? themeObject?.primary;
  const logo = value("logo_url") ?? data.logo_path;
  const currency = value("currency");
  const timezone = value("timezone");
  const rawTheme = value("theme");
  const theme = typeof rawTheme === "string" ? rawTheme : null;
  const defaultDarkMode =
    themeObject?.default_color_scheme === "dark" ||
    merged.default_dark_mode === true;

  const responseSlug = typeof data.slug === "string" ? data.slug : requestedSlug;
  if (responseSlug !== requestedSlug && requestedSlug !== DEFAULT_TENANT_SLUG) {
    return { ...fallback };
  }

  return {
    id: data.tenant_id ?? data.id ?? null,
    slug: responseSlug,
    brand_name:
      typeof value("brand_name") === "string"
        ? (value("brand_name") as string)
        : fallback.brand_name,
    logo_url:
      typeof logo === "string" && isLogoUrl(logo) ? logo : fallback.logo_url,
    primary_color:
      typeof primary === "string" ? primary.toUpperCase() : fallback.primary_color,
    theme: isTheme(theme) ? theme : fallback.theme,
    default_dark_mode:
      theme === "dark" || (theme !== "light" && defaultDarkMode),
    currency:
      typeof currency === "string" &&
      (() => {
        try {
          new Intl.NumberFormat("en", { style: "currency", currency });
          return true;
        } catch {
          return false;
        }
      })()
        ? currency
        : fallback.currency,
    timezone:
      typeof timezone === "string" && isTimezone(timezone)
        ? timezone
        : fallback.timezone,
    date_format:
      typeof value("date_format") === "string"
        ? (value("date_format") as string)
        : fallback.date_format,
  };
}

export function brandingStyles(
  branding: TenantBranding,
  background: string = "#F5F2EB",
): Record<string, string> {
  return {
    "--brand-primary": branding.primary_color,
    "--brand-primary-accessible": accessiblePrimaryColor(branding.primary_color),
    "--brand-primary-deep": accessiblePrimaryColor(branding.primary_color),
    "--brand-on-primary": contrastRatio(branding.primary_color, "#FFFFFF") >= 4.5
      ? "#FFFFFF"
      : "#202923",
    "--brand-radius": "0.75rem",
    "--tenant-background": background,
  };
}

export function applyBrandingBootstrap(
  target?: Pick<Document, "documentElement">,
): TenantBranding {
  const branding = { ...DEFAULT_BRANDING };
  const root = target?.documentElement ?? document.documentElement;
  for (const [property, value] of Object.entries(brandingStyles(branding))) {
    root.style.setProperty(property, value);
  }
  root.dataset.tenant = branding.slug;
  root.style.colorScheme = "light";
  return branding;
}
