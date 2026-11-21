import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  ChevronRight,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  UserCog,
  X,
} from "lucide-react";
import { clearOperatorSession } from "./session";
import { useOperator } from "./OperatorAuthGuard";
import type { OperatorPermission } from "./operatorModel";
import { Logo } from "../components/Logo";

interface OperatorNavItem {
  label: string;
  to: string;
  icon: typeof LayoutDashboard;
  permission: OperatorPermission;
  end?: boolean;
}

const NAV_ITEMS: OperatorNavItem[] = [
  {
    label: "Tenants",
    to: "/operator",
    icon: LayoutDashboard,
    permission: "tenants.read",
    end: true,
  },
  {
    label: "Plans",
    to: "/operator/plans",
    icon: CreditCard,
    permission: "tenants.read",
  },
  {
    label: "Operators",
    to: "/operator/operators",
    icon: UserCog,
    permission: "operators.manage",
  },
  {
    label: "Audit log",
    to: "/operator/audit-logs",
    icon: ScrollText,
    permission: "audit.read",
  },
];

export function OperatorLayout() {
  const { operator, can } = useOperator();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const visibleItems = NAV_ITEMS.filter((item) => can(item.permission));
  const initials =
    operator.full_name
      .split(/\s+/)
      .map((part) => part[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "OP";

  useEffect(() => {
    setMenuOpen(false);
    document.title = "PropFlow Operator Console";
  }, [location.pathname]);

  const signOut = () => {
    clearOperatorSession();
    navigate("/operator/login", { replace: true });
  };

  return (
    <div className="min-h-svh bg-[#FAFAF7] text-charcoal">
      <a
        href="#operator-main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[60] focus:rounded-full focus:bg-charcoal focus:px-5 focus:py-3 focus:text-sm focus:font-semibold focus:text-ivory"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-30 border-b border-charcoal/10 bg-[#FAFAF7]/95 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 lg:h-[4.5rem] lg:px-8">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open operator navigation"
              className="grid size-10 place-items-center rounded-xl border border-charcoal/10 text-charcoal/70 transition-colors hover:bg-charcoal/5 lg:hidden"
            >
              <Menu aria-hidden="true" className="size-5" />
            </button>
            <Logo href="/operator" />
            <span className="hidden rounded-full border border-forest/20 bg-forest/10 px-2.5 py-1 text-[0.6rem] font-semibold tracking-[0.15em] text-forest-deep uppercase sm:inline-flex">
              Operator
            </span>
          </div>

          <nav aria-label="Operator navigation" className="hidden items-center gap-1 lg:flex">
            {visibleItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-colors ${
                      isActive
                        ? "bg-charcoal text-ivory"
                        : "text-charcoal/65 hover:bg-charcoal/5 hover:text-charcoal"
                    }`
                  }
                >
                  <Icon aria-hidden="true" className="size-4" />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="flex items-center gap-2.5">
            <div className="hidden items-center gap-2.5 border-r border-charcoal/10 pr-3 sm:flex">
              <span className="grid size-8 place-items-center rounded-lg bg-charcoal text-[0.65rem] font-bold text-ivory">
                {initials}
              </span>
              <div className="hidden text-right xl:block">
                <p className="max-w-36 truncate text-xs font-semibold">{operator.full_name}</p>
                <p className="text-[0.6rem] font-medium tracking-wider text-charcoal/50 uppercase">
                  {operator.role}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={signOut}
              className="inline-flex size-10 items-center justify-center rounded-xl border border-charcoal/10 text-charcoal/65 transition-colors hover:bg-charcoal/5 hover:text-charcoal lg:size-auto lg:gap-2 lg:px-3 lg:py-2 lg:text-xs lg:font-semibold"
            >
              <LogOut aria-hidden="true" className="size-4" />
              <span className="hidden lg:inline">Sign out</span>
              <span className="sr-only lg:hidden">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main id="operator-main" tabIndex={-1} className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <Outlet />
      </main>

      <footer className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 pb-6 text-[0.65rem] text-charcoal/45 sm:px-6 lg:px-8">
        <span>PropFlow control plane · operator actions are audited</span>
        {can("tenants.write") ? (
          <Link to="/operator/tenants/new" className="inline-flex items-center gap-1 font-semibold text-forest">
            Provision tenant
            <ChevronRight aria-hidden="true" className="size-3" />
          </Link>
        ) : null}
      </footer>

      {menuOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close operator navigation"
            onClick={() => setMenuOpen(false)}
            className="absolute inset-0 bg-charcoal/45 backdrop-blur-xs"
          />
          <div className="relative flex h-full w-[min(20rem,calc(100vw-3rem))] flex-col bg-[#FAFAF7] p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-charcoal/10 pb-4">
              <Logo href="/operator" />
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close operator navigation"
                className="rounded-lg p-1.5 text-charcoal/60 hover:bg-charcoal/5"
              >
                <X aria-hidden="true" className="size-5" />
              </button>
            </div>

            <nav aria-label="Mobile operator navigation" className="mt-5 space-y-1">
              {visibleItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-semibold transition-colors ${
                        isActive
                          ? "bg-charcoal text-ivory"
                          : "text-charcoal/70 hover:bg-charcoal/5"
                      }`
                    }
                  >
                    <Icon aria-hidden="true" className="size-[18px]" />
                    {item.label}
                  </NavLink>
                );
              })}
            </nav>

            <div className="mt-auto border-t border-charcoal/10 pt-4">
              <div className="flex items-center gap-3 rounded-xl border border-charcoal/10 bg-white p-3">
                <span className="grid size-9 place-items-center rounded-lg bg-charcoal text-xs font-bold text-ivory">
                  {initials}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold">{operator.full_name}</p>
                  <p className="truncate text-[0.65rem] text-charcoal/55">{operator.email}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={signOut}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-charcoal/15 px-3 py-2.5 text-xs font-semibold text-clay"
              >
                <LogOut aria-hidden="true" className="size-3.5" />
                Sign out
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
