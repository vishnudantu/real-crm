import { z } from "zod";
import { API_BASE_URL, ApiError } from "../auth/api";
import { getSession } from "../auth/session";
import type { ErrorDetail } from "../auth/api";
import { normalizeBranding, resolveTenantSlug } from "./branding";
import type {
  TenantBranding,
  UpdateTenantBrandingPayload,
} from "./types";

const updateBrandingSchema = z.object({
  brand_name: z.string().trim().min(1, "Enter a brand name.").max(100),
  logo_url: z
    .string()
    .trim()
    .max(2048)
    .nullable()
    .refine(
      (value) =>
        value === null ||
        value === "" ||
        value.startsWith("/") ||
        value.startsWith("https://") ||
        value.startsWith("http://localhost") ||
        value.startsWith("http://127.0.0.1"),
      "Enter a relative path or HTTPS logo URL.",
    ),
  primary_color: z
    .string()
    .regex(/^#[\dA-Fa-f]{6}$/, "Choose a six-digit hex color."),
  theme: z.enum(["light", "dark", "SYSTEM"]),
  default_dark_mode: z.boolean(),
  currency: z.string().trim().regex(/^[A-Z]{3}$/, "Use an ISO currency code."),
  timezone: z
    .string()
    .trim()
    .min(1)
    .refine((value) => {
      try {
        new Intl.DateTimeFormat("en", { timeZone: value });
        return true;
      } catch {
        return false;
      }
    }, "Enter a valid IANA timezone."),
  date_format: z.string().trim().regex(/^[dDMyY,./\- ]{4,24}$/),
});

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function responseError(response: Response, payload: unknown): ApiError {
  const error =
    typeof payload === "object" && payload !== null && "error" in payload
      ? (payload as { error?: { code?: unknown; message?: unknown; details?: unknown } }).error
      : undefined;
  const details = Array.isArray(error?.details)
    ? (error.details as ErrorDetail[])
    : [];
  return new ApiError(
    response.status,
    typeof error?.code === "string" ? error.code : `HTTP_${response.status}`,
    typeof error?.message === "string"
      ? error.message
      : "The branding request could not be completed.",
    details,
  );
}

export async function fetchPublicBranding(
  slug: string = resolveTenantSlug(),
  signal?: AbortSignal,
): Promise<TenantBranding> {
  const resolvedSlug = resolveTenantSlug(slug);
  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/tenancy/public/${encodeURIComponent(resolvedSlug)}`,
      { headers: { Accept: "application/json" }, signal },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "BRANDING_UNAVAILABLE",
      "Tenant branding is unavailable; the default visual theme will be used.",
    );
  }

  const payload = await parseJson(response);
  if (!response.ok) throw responseError(response, payload);
  return normalizeBranding(payload, undefined, resolvedSlug);
}

export async function fetchTenantBranding(
  signal?: AbortSignal,
): Promise<TenantBranding> {
  const response = await authenticatedBrandingRequest<unknown>(
    "/tenancy/settings",
    { signal },
  );
  return normalizeBranding(response);
}

export async function updateTenantBranding(
  payload: UpdateTenantBrandingPayload,
): Promise<TenantBranding> {
  const validated = updateBrandingSchema.parse({
    ...payload,
    logo_url: payload.logo_url?.trim() || null,
  });
  const result = await authenticatedBrandingRequest<unknown>("/tenancy/settings", {
    method: "PUT",
    body: JSON.stringify({
      brand_name: validated.brand_name,
      logo_path: validated.logo_url || null,
      theme: {
        primary: validated.primary_color,
        default_color_scheme: validated.default_dark_mode ? "dark" : "light",
      },
      currency: validated.currency,
      timezone: validated.timezone,
      date_format: validated.date_format,
    }),
  });
  return normalizeBranding(result);
}

async function authenticatedBrandingRequest<T>(
  path: string,
  init: RequestInit,
): Promise<T> {
  const session = getSession();
  if (!session?.accessToken) {
    throw new ApiError(401, "UNAUTHORIZED", "Active administrator session required.");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${session.accessToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "NETWORK_ERROR", "Failed to reach the branding service.");
  }

  const payload = await parseJson(response);
  if (!response.ok) throw responseError(response, payload);
  return payload as T;
}
