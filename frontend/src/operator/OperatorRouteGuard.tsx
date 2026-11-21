import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useOperator } from "./OperatorAuthGuard";
import type { OperatorPermission } from "./operatorModel";

export function operatorHomePath(
  can: (permission: OperatorPermission) => boolean,
): string {
  if (can("tenants.read")) return "/operator";
  if (can("operators.manage")) return "/operator/operators";
  if (can("audit.read")) return "/operator/audit-logs";
  return "/operator/access";
}

interface OperatorRouteGuardProps {
  permission?: OperatorPermission;
  children: ReactNode;
}

export function OperatorRouteGuard({
  permission,
  children,
}: OperatorRouteGuardProps) {
  const { can } = useOperator();
  const location = useLocation();
  const homePath = operatorHomePath(can);

  if (location.pathname === "/operator" && homePath !== "/operator") {
    return <Navigate to={homePath} replace />;
  }
  if (permission && !can(permission)) {
    if (location.pathname === homePath) return children;
    return <Navigate to={homePath} replace />;
  }

  return children;
}

export function OperatorNoAccessPage() {
  const { operator } = useOperator();
  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-charcoal/10 bg-white p-8 text-center shadow-xs">
      <ShieldAlert aria-hidden="true" className="mx-auto size-8 text-charcoal/40" />
      <h1 className="mt-4 text-xl font-semibold text-charcoal">No console permissions</h1>
      <p className="mt-2 text-sm leading-6 text-charcoal/60">
        {operator.full_name} has no views assigned. Contact a PropFlow owner to
        update this operator account's role or additional permissions.
      </p>
      <Link to="/operator/login" className="mt-5 inline-flex text-xs font-semibold text-forest">
        Return to operator sign in
      </Link>
    </div>
  );
}
