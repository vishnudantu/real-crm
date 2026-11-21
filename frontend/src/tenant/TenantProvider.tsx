import { createContext, useContext, useEffect } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPublicBranding } from "./api";
import { ApiError } from "../auth/api";
import {
  brandingStyles,
  DEFAULT_BRANDING,
  resolveTenantSlug,
} from "./branding";
import type { TenantContextValue } from "./types";

const TenantContext = createContext<TenantContextValue | null>(null);
const BRANDING_STALE_TIME = 5 * 60 * 1000;
const BRANDING_UNAVAILABLE_STATUSES = new Set([401, 403, 404, 405, 501]);

export function publicBrandingQueryKey(slug: string): readonly ["tenant", "branding", string] {
  return ["tenant", "branding", resolveTenantSlug(slug)];
}

interface TenantProviderProps {
  children: ReactNode;
  slug?: string;
}

export function TenantProvider({ children, slug }: TenantProviderProps) {
  const resolvedSlug = resolveTenantSlug(slug);
  const query = useQuery({
    queryKey: publicBrandingQueryKey(resolvedSlug),
    queryFn: ({ signal }) => fetchPublicBranding(resolvedSlug, signal),
    initialData: { ...DEFAULT_BRANDING, slug: resolvedSlug },
    initialDataUpdatedAt: 0,
    staleTime: BRANDING_STALE_TIME,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: (failureCount, error) =>
      !(error instanceof ApiError &&
        (BRANDING_UNAVAILABLE_STATUSES.has(error.status) || error.status === 0)) &&
      failureCount < 1,
  });

  const branding = query.data ?? { ...DEFAULT_BRANDING, slug: resolvedSlug };

  useEffect(() => {
    const root = document.documentElement;
    for (const [property, value] of Object.entries(brandingStyles(branding))) {
      root.style.setProperty(property, value);
    }
    root.dataset.tenant = branding.slug;
    root.dataset.brand = branding.brand_name;
    root.dataset.theme = branding.theme;
    root.style.colorScheme = branding.default_dark_mode ? "dark" : "light";
  }, [branding]);

  useEffect(() => {
    // Only the landing page inherits the tenant-branded title; individual
    // pages (login, portal routes) set and restore their own document titles.
    if (window.location.pathname !== "/") return;
    document.title = `${branding.brand_name} — AI enquiry desk`;
  }, [branding.brand_name]);

  return (
    <TenantContext.Provider
      value={{
        branding,
        isLoading: query.isFetching,
        isUsingDefaults: !query.isSuccess,
        error: query.error,
        refresh: query.refetch,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant(): TenantContextValue {
  const context = useContext(TenantContext);
  if (!context) throw new Error("useTenant must be used within TenantProvider");
  return context;
}

export { profileMatchesTenant } from "./profile";
