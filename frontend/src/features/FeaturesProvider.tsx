import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { API_BASE_URL } from "../auth/api";
import { getSession } from "../auth/session";
import { useTenant } from "../tenant/TenantProvider";
import { bearerRequest } from "../shared/apiRequest";

export type FeatureKey = string;
export type FeatureMap = Record<FeatureKey, boolean>;

interface FeaturesContextValue {
  features: FeatureMap;
  isLoading: boolean;
  enabled: (key: FeatureKey) => boolean;
  refresh: () => Promise<void>;
}

const FeaturesContext = createContext<FeaturesContextValue | null>(null);

export function FeaturesProvider({ children }: { children: ReactNode }) {
  const { branding } = useTenant();
  const [features, setFeatures] = useState<FeatureMap>({});
  const [isLoading, setIsLoading] = useState(true);

  const load = async () => {
    const session = getSession();
    if (!session?.accessToken) {
      setFeatures({});
      setIsLoading(false);
      return;
    }
    try {
      const data = await bearerRequest<FeatureMap>("/tenancy/me/features", {
        getToken: getSession,
        clearToken: () => {},
      });
      setFeatures(data);
    } catch {
      // Feature discovery failure must not block navigation; keep conservative
      // defaults (core features on) so the console still works offline.
      setFeatures((current) => current);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // Re-resolve when the active tenant changes.
  }, [branding.id]);

  const value = useMemo<FeaturesContextValue>(
    () => ({
      features,
      isLoading,
      enabled: (key) => features[key] ?? false,
      refresh: load,
    }),
    [features, isLoading],
  );

  return (
    <FeaturesContext.Provider value={value}>{children}</FeaturesContext.Provider>
  );
}

export function useFeatures(): FeaturesContextValue {
  const context = useContext(FeaturesContext);
  if (!context) {
    throw new Error("useFeatures must be used within a FeaturesProvider");
  }
  return context;
}

export const FEATURE_API_BASE = API_BASE_URL;
