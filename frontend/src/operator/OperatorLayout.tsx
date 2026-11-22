import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Building2,
  ChevronRight,
  CreditCard,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  ShieldAlert,
  Sparkles,
  UserCog,
  WandSparkles,
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

interface OperatorNavGroup {
  title: string;
  items: OperatorNavItem[];
}

const NAV_GROUPS: OperatorNavGroup[] = [
  {
    title: "Mission Control",
    items: [
      {
        label: "Platform Overview",
        to: "/operator",
        icon: Gauge,
        permission: "tenants.read",
        end: true,
      },
      {
        label: "Incidents",
        to: "/operator/incidents",
        icon: ShieldAlert,
        permission: "tenants.read",
      },
    ],
  },
  {
    title: "Organizations",
    items: [
      {
        label: "Tenant Directory",
        to: "/operator/tenants",
        icon: Building2,
        permission: "tenants.read",
        end: true,
      },
      {
        label: "Onboarding",
        to: "/operator/tenants/new",
        icon: WandSparkles,
        permission: "tenants.write",
      },
    ],
  },
  {
    title: "Revenue",
    items: [
      {
        label: "Plans & Entitlements",
        to: "/operator/plans",
        icon: CreditCard,
        permission: "tenants.read",
      },
    ],
  },
  {
    title: "Trust & Access",
    items: [
      {
        label: "Operator Directory",
        to: "/operator/operators",
        icon: UserCog,
        permission: "operators.manage",
      },
      {
        label: "Audit Explorer",
        to: "/operator/audit-logs",
        icon: ScrollText,
        permission: "audit.read",
      },
    ],
  },
];

const SIDEBAR_STORAGE_KEY = "propflow.operator.sidebar-collapsed";

function itemForPath(pathname: string): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const matched = item.end
        ? pathname === item.to
        : pathname === item.to || pathname.startsWith(`${item.to}/`);
      if (matched) return `${group.title} · ${item.label}`;
    }
  }
  if (/^\/operator\/tenants\/[^/]+$/.test(pathname)) {
    return "Organizations · Tenant 360";
  }
  return "Operator Console";
}

export function OperatorLayout() {
  const { operator, can } = useOperator();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    } catch {
      // Sidebar preference persistence is optional.
    }
  }, [collapsed]);

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => can(item.permission)),
  })).filter((group) => group.items.length > 0);
  const initials =
    operator.full_name
      .split(/\s+/)
      .map((part) => part[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "OP";

  useEffect(() => {
    setMenuOpen(false);
    document.title = `PropFlow Operator Console`;
  }, [location.pathname]);

  const signOut = () => {
    clearOperatorSession();
    navigate("/operator/login", { replace: true });
  };

  const sidebarLinkClass = ({ isActive }: { isActive: boolean }) =>
    [
      "relative flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-colors",
      collapsed ? "justify-center px-2" : "px-3.5",
      isActive
        ? "bg-charcoal font-semibold text-ivory shadow-xs"
        : "text-charcoal/75 hover:bg-charcoal/5 hover:text-charcoal",
    ].join(" ");

  return (
    <div className="min-h-svh bg-[#FAFAF7] text-charcoal">
      <a
        href="#operator-main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[60] focus:rounded-full focus:bg-charcoal focus:px-5 focus:py-3 focus:text-sm focus:font-semibold focus:text-ivory"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        aria-label="Operator console navigation"
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col justify-between border-r border-charcoal/10 bg-white/95 backdrop-blur-md transition-[width] duration-200 lg:flex ${
          collapsed ? "w-[84px]" : "w-[272px]"
        }`}
      >
        <div className="min-h-0 overflow-y-auto">
          <div
            className={`flex h-20 items-center border-b border-charcoal/10 ${
              collapsed ? "justify-center px-2" : "justify-between px-5"
            }`}
          >
            <Logo
              href="/operator"
              tone="dark"
              className={collapsed ? "[&>span:last-child]:hidden" : ""}
            />
            {!collapsed ? (
              <span className="rounded-full border border-forest/20 bg-forest/10 px-2.5 py-1 text-[0.6rem] font-semibold tracking-[0.15em] text-forest uppercase">
                Operator
              </span>
            ) : null}
          </div>

          <nav aria-label="Primary operator navigation" className={collapsed ? "px-2 py-6" : "px-3.5 py-6"}>
            {visibleGroups.map((group) => (
              <div key={group.title} className="mb-6 last:mb-0">
                {!collapsed ? (
                  <p className="mb-2 px-3 text-[0.62rem] font-semibold tracking-[0.2em] text-charcoal/50 uppercase">
                    {group.title}
                  </p>
                ) : (
                  <div aria-hidden="true" className="mx-auto mb-3 h-px w-8 bg-charcoal/10" />
                )}
                <ul className="space-y-1">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    return (
                      <li key={item.to}>
                        <NavLink
                          to={item.to}
                          end={item.end}
                          title={collapsed ? item.label : undefined}
                          className={sidebarLinkClass}
                        >
                          {({ isActive }) => (
                            <>
                              <Icon
                                aria-hidden="true"
                                className={`size-[18px] shrink-0 ${
                                  isActive ? "text-ivory" : "text-charcoal/65"
                                }`}
                              />
                              <span className={collapsed ? "sr-only" : "truncate"}>
                                {item.label}
                              </span>
                              {!collapsed && isActive ? (
                                <span
                                  aria-hidden="true"
                                  className="ml-auto size-1.5 rounded-full bg-sand"
                                />
                              ) : null}
                            </>
                          )}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </div>

        <div className={`border-t border-charcoal/10 p-3.5 ${collapsed ? "px-2" : ""}`}>
          <button
            type="button"
            onClick={() => setCollapsed((previous) => !previous)}
            aria-label={collapsed ? "Expand operator sidebar" : "Collapse operator sidebar"}
            className={
              collapsed
                ? "mx-auto flex size-10 items-center justify-center rounded-xl border border-charcoal/10 text-charcoal/70 transition-colors hover:border-charcoal/25 hover:bg-charcoal/5 hover:text-charcoal"
                : "flex w-full items-center gap-2 rounded-xl border border-charcoal/10 px-3 py-2 text-xs font-semibold text-charcoal/70 transition-colors hover:border-charcoal/25 hover:bg-charcoal/5 hover:text-charcoal"
            }
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" className="size-4" />
            ) : (
              <>
                <PanelLeftClose aria-hidden="true" className="size-4" />
                Collapse sidebar
              </>
            )}
          </button>
          <div className={`flex items-center gap-2.5 py-3 ${collapsed ? "justify-center" : "px-1"}`}>
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-charcoal text-[0.65rem] font-bold text-ivory">
              {initials}
            </span>
            {!collapsed ? (
              <div className="min-w-0">
                <p className="max-w-36 truncate text-xs font-semibold">{operator.full_name}</p>
                <p className="truncate text-[0.6rem] font-medium tracking-wider text-charcoal/50 uppercase">
                  {operator.role}
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </aside>

      {/* Top bar (mobile + breadcrumb strip) */}
      <header className="sticky top-0 z-20 border-b border-charcoal/10 bg-[#FAFAF7]/95 backdrop-blur-md lg:pl-[84px] xl:pl-[272px]">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open operator navigation"
              className="grid size-10 place-items-center rounded-xl border border-charcoal/10 text-charcoal/70 transition-colors hover:bg-charcoal/5 lg:hidden"
            >
              <Menu aria-hidden="true" className="size-5" />
            </button>
            <div className="hidden min-w-0 lg:block">
              <p className="truncate text-xs font-semibold text-charcoal/80">
                {itemForPath(location.pathname)}
              </p>
            </div>
            <Logo href="/operator" className="lg:hidden" />
          </div>

          <div className="flex items-center gap-2.5">
            {can("tenants.write") ? (
              <Link
                to="/operator/tenants/new"
                className="hidden items-center gap-1.5 rounded-xl bg-forest px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-forest-deep sm:inline-flex"
              >
                <Sparkles aria-hidden="true" className="size-3.5" />
                Onboard tenant
              </Link>
            ) : null}
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

      <main
        id="operator-main"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1600px] px-4 py-6 transition-[padding] duration-200 sm:px-6 lg:px-8 lg:py-8 lg:pl-[calc(84px+2rem)] xl:pl-[calc(272px+2rem)]"
      >
        <Outlet />
      </main>

      <footer className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 pb-6 text-[0.65rem] text-charcoal/45 sm:px-6 lg:px-8 lg:pl-[calc(84px+2rem)] xl:pl-[calc(272px+2rem)]">
        <span>PropFlow control plane · operator actions are audited</span>
        <Link to="/operator/audit-logs" className="inline-flex items-center gap-1 font-semibold text-forest">
          Audit trail
          <ChevronRight aria-hidden="true" className="size-3" />
        </Link>
      </footer>

      {/* Mobile drawer */}
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

            <nav aria-label="Mobile operator navigation" className="mt-5 min-h-0 flex-1 space-y-5 overflow-y-auto">
              {visibleGroups.map((group) => (
                <div key={group.title}>
                  <p className="mb-1.5 px-2 text-[0.6rem] font-semibold tracking-[0.2em] text-charcoal/50 uppercase">
                    {group.title}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => {
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
                  </div>
                </div>
              ))}
            </nav>

            <div className="mt-4 border-t border-charcoal/10 pt-4">
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
