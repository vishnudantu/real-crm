import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { fetchOperatorProfile } from "./api";
import { clearOperatorSession, getOperatorSession } from "./session";
import type { OperatorPermission, OperatorUser } from "./operatorModel";
import { Logo } from "../components/Logo";

interface OperatorContextValue {
  operator: OperatorUser;
  can: (permission: OperatorPermission) => boolean;
  refreshOperator: () => Promise<void>;
}

const ROLE_PERMISSIONS: Record<OperatorUser["role"], OperatorPermission[]> = {
  OWNER: [
    "tenants.read",
    "tenants.write",
    "plans.write",
    "deployments.write",
    "operators.manage",
    "audit.read",
    "tenants.impersonate",
    "revenue.read",
  ],
  SUPPORT: ["tenants.read", "audit.read"],
  SALES: ["tenants.read", "tenants.write", "audit.read"],
  DEPLOYER: ["tenants.read", "deployments.write"],
};

export function operatorHasPermission(
  operator: OperatorUser,
  permission: OperatorPermission,
): boolean {
  return (
    ROLE_PERMISSIONS[operator.role]?.includes(permission) ||
    operator.permissions.includes(permission)
  );
}

const OperatorContext = createContext<OperatorContextValue | null>(null);

export function useOperator(): OperatorContextValue {
  const context = useContext(OperatorContext);
  if (!context) throw new Error("useOperator must be used within OperatorAuthGuard");
  return context;
}

interface OperatorProviderProps {
  operator: OperatorUser;
  children: ReactNode;
}

export function OperatorProvider({ operator, children }: OperatorProviderProps) {
  const [current, setCurrent] = useState(operator);

  const refreshOperator = useCallback(async () => {
    const updated = await fetchOperatorProfile();
    setCurrent(updated);
  }, []);

  const can = useCallback(
    (permission: OperatorPermission) => operatorHasPermission(current, permission),
    [current],
  );

  const value = useMemo(
    () => ({ operator: current, can, refreshOperator }),
    [current, can, refreshOperator],
  );

  return (
    <OperatorContext.Provider value={value}>
      {children}
    </OperatorContext.Provider>
  );
}

type GuardStatus = "loading" | "authenticated" | "unauthorized";

export function OperatorAuthGuard() {
  const location = useLocation();
  const [operator, setOperator] = useState<OperatorUser | null>(null);
  const [status, setStatus] = useState<GuardStatus>("loading");

  useEffect(() => {
    let active = true;

    async function verify() {
      const session = getOperatorSession();
      if (!session?.accessToken) {
        if (active) setStatus("unauthorized");
        return;
      }

      try {
        const profile = await fetchOperatorProfile();
        if (!active) return;
        setOperator(profile);
        setStatus("authenticated");
      } catch {
        if (!active) return;
        clearOperatorSession();
        setStatus("unauthorized");
      }
    }

    void verify();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const session = getOperatorSession();
    if (!session) return;

    const expire = () => {
      clearOperatorSession();
      setOperator(null);
      setStatus("unauthorized");
    };
    const remaining = session.expiresAt - Date.now();
    if (remaining <= 0) {
      expire();
      return;
    }

    const timer = window.setTimeout(expire, remaining);
    const revalidate = () => {
      if (document.visibilityState === "hidden") return;
      if (!getOperatorSession()) expire();
    };
    window.addEventListener("focus", revalidate);
    document.addEventListener("visibilitychange", revalidate);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("focus", revalidate);
      document.removeEventListener("visibilitychange", revalidate);
    };
  }, [status]);

  if (status === "loading") {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-4 bg-ivory text-charcoal">
        <Logo href="/operator" />
        <div className="flex items-center gap-2 text-sm text-charcoal/65">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Verifying operator access…
        </div>
      </div>
    );
  }

  if (status === "unauthorized" || !operator) {
    return <Navigate to="/operator/login" state={{ from: location }} replace />;
  }

  return (
    <OperatorProvider operator={operator}>
      <Outlet />
    </OperatorProvider>
  );
}
