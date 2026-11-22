import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { clearSession } from "../auth/session";
import { Logo } from "../components/Logo";
import { useAdminUser } from "./AdminAuthGuard";
import { useTenant } from "../tenant/TenantProvider";
import { useFeatures } from "../features/FeaturesProvider";
import { buildAdminMobileNav, buildAdminNav } from "./adminNavigation";
import type { AdminNavigationItem } from "./adminNavigation";
import { adminNavigationIcon } from "./adminNavigationIcons";
import { AdminNavigationSections } from "./AdminNavigationSections";
import { logoutRequest } from "../auth/api";

const SIDEBAR_STORAGE_KEY = "propflow.admin.sidebar-collapsed";
const SETTINGS_OPEN_STORAGE_KEY = "propflow.admin.settings-open";

function readStorageFlag(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}

function isPathActive(pathname: string, item: AdminNavigationItem): boolean {
  return item.exact
    ? pathname === item.to || pathname === `${item.to}/overview`
    : pathname === item.to || pathname.startsWith(`${item.to}/`);
}

export function AdminLayout() {
  const { user } = useAdminUser();
  const { branding } = useTenant();
  const { features } = useFeatures();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const shouldReduceMotion = useReducedMotion();
  const groups = useMemo(() => buildAdminNav(features), [features]);
  const mobilePrimary = useMemo(() => buildAdminMobileNav(features), [features]);
  const items = useMemo(() => groups.flatMap((group) => group.items), [groups]);
  const currentItem = items
    .flatMap((item) => [...(item.children ?? []), item])
    .find((item) => isPathActive(pathname, item));
  const pageLabel = currentItem?.label ?? "Admin Console";

  const [collapsed, setCollapsed] = useState(() => readStorageFlag(SIDEBAR_STORAGE_KEY));
  const [settingsOpen, setSettingsOpen] = useState(
    () => pathname.startsWith("/admin/settings") || readStorageFlag(SETTINGS_OPEN_STORAGE_KEY),
  );
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  const initials = user.full_name
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() || "AD";
  const firstName = user.full_name.split(/\s+/)[0] || "Admin";

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    } catch {
      // Preference persistence is optional in restricted browsing modes.
    }
  }, [collapsed]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SETTINGS_OPEN_STORAGE_KEY, String(settingsOpen));
    } catch {
      // Preference persistence is optional in restricted browsing modes.
    }
  }, [settingsOpen]);

  useEffect(() => {
    if (pathname.startsWith("/admin/settings")) setSettingsOpen(true);
  }, [pathname]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${pageLabel} — ${branding.brand_name} Admin Console`;
    return () => {
      document.title = previousTitle;
    };
  }, [pageLabel, branding.brand_name]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerRef.current
      ?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')?.[0]
      ?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const nodes = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'),
      );
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      menuButtonRef.current?.focus();
    };
  }, [mobileMenuOpen]);

  const handleSignOut = async () => {
    try {
      await logoutRequest();
    } catch {
      // Local sign-out still succeeds if the API cannot be reached.
    } finally {
      clearSession();
      navigate("/login", { replace: true });
    }
  };

  const formattedDate = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date());

  return (
    <div className="flex min-h-screen flex-col bg-[#FAFAF7] font-sans text-charcoal">
      <a href="#admin-main" className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[60] focus:rounded-full focus:bg-charcoal focus:px-5 focus:py-3 focus:text-sm focus:font-semibold focus:text-ivory">
        Skip to main content
      </a>

      <aside
        id="admin-sidebar"
        aria-label="Admin console navigation"
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-charcoal/10 bg-white/95 backdrop-blur-md transition-[width] duration-300 ease-out lg:flex ${collapsed ? "w-[84px]" : "w-[272px]"}`}
      >
        <div className={`flex h-20 shrink-0 items-center border-b border-charcoal/10 ${collapsed ? "justify-center px-2" : "justify-between px-5"}`}>
          <Logo href="/admin" tone="dark" className={collapsed ? "[&>span:last-child]:hidden" : ""} />
          {!collapsed && <span className="rounded-full border border-charcoal/15 bg-charcoal/5 px-2.5 py-1 text-[0.6rem] font-semibold tracking-wider uppercase">Admin</span>}
        </div>

        <nav aria-label="Primary Admin Navigation" className={`min-h-0 flex-1 overflow-y-auto ${collapsed ? "px-2 py-5" : "px-3.5 py-5"}`}>
          <AdminNavigationSections
            groups={groups}
            collapsed={collapsed}
            settingsOpen={settingsOpen}
            onSettingsOpenChange={setSettingsOpen}
          />
        </nav>

        <div className={`shrink-0 border-t border-charcoal/10 ${collapsed ? "space-y-2 p-2" : "space-y-2.5 p-4"}`}>
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            aria-expanded={!collapsed}
            aria-controls="admin-sidebar"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : undefined}
            className={collapsed
              ? "mx-auto flex size-10 items-center justify-center rounded-xl border border-charcoal/10 text-charcoal/70 transition-colors hover:bg-charcoal/5"
              : "flex w-full items-center gap-2 rounded-xl border border-charcoal/10 px-3 py-2 text-xs font-semibold text-charcoal/70 transition-colors hover:bg-charcoal/5"}
          >
            {collapsed ? <PanelLeftOpen aria-hidden="true" className="size-4" /> : <><PanelLeftClose aria-hidden="true" className="size-4" /><span>Collapse sidebar</span></>}
          </button>

          {collapsed ? (
            <>
              <Link to="/admin/account" title="My Account" className="mx-auto grid size-10 place-items-center rounded-xl bg-charcoal text-xs font-bold text-ivory shadow-xs">{initials}</Link>
              <button type="button" onClick={() => void handleSignOut()} aria-label="Sign out" title="Sign out" className="mx-auto flex size-10 items-center justify-center rounded-xl border border-charcoal/10 text-charcoal/70 hover:bg-rose-50 hover:text-rose-600"><LogOut aria-hidden="true" className="size-4" /></button>
            </>
          ) : (
            <>
              <Link to="/admin/account" className="flex items-center gap-2.5 rounded-xl border border-charcoal/10 bg-[#FAFAF7] p-2.5 shadow-xs transition-colors hover:border-charcoal/25">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-charcoal text-xs font-bold text-ivory">{initials}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{user.full_name}</span><span className="block truncate text-[0.68rem] font-medium tracking-wider text-charcoal/50 uppercase">Administrator</span></span>
              </Link>
              <button type="button" onClick={() => void handleSignOut()} className="flex w-full items-center justify-center gap-2 rounded-xl border border-charcoal/15 px-3 py-2 text-xs font-semibold text-charcoal/70 hover:bg-charcoal/5"><LogOut aria-hidden="true" className="size-3.5" /><span>Sign out</span></button>
            </>
          )}
        </div>
      </aside>

      <div className={`flex flex-1 flex-col transition-[padding] duration-300 ease-out ${collapsed ? "lg:pl-[84px]" : "lg:pl-[272px]"}`}>
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-charcoal/10 bg-[#FAFAF7]/95 px-4 backdrop-blur-md sm:px-6 lg:h-20 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button ref={menuButtonRef} type="button" onClick={() => setMobileMenuOpen(true)} aria-label="Open navigation menu" aria-expanded={mobileMenuOpen} className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-charcoal/10 hover:bg-charcoal/5 lg:hidden"><Menu aria-hidden="true" className="size-5" /></button>
            <div className="lg:hidden"><Logo href="/admin" tone="dark" /></div>
            <div className="hidden min-w-0 items-center gap-2 lg:flex"><span className="text-[0.66rem] font-semibold tracking-[0.2em] text-charcoal/60 uppercase">Admin Console</span><span aria-hidden="true" className="text-charcoal/30">/</span><span className="truncate text-xs font-semibold">{pageLabel}</span></div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-800 md:flex"><span className="size-1.5 animate-pulse rounded-full bg-emerald-500" /><span>Operational</span></div>
            <span className="hidden text-[0.68rem] font-medium text-charcoal/60 xl:inline">{formattedDate}</span>
            <Link to="/admin/account" aria-label="My Account" className="grid size-9 place-items-center rounded-full bg-charcoal text-xs font-bold text-ivory lg:hidden">{initials}</Link>
            <Link to="/admin/account" className="hidden items-center gap-2.5 rounded-full border border-charcoal/10 bg-white/80 py-1 pr-3 pl-1.5 shadow-xs lg:flex"><span className="grid size-7 place-items-center rounded-full bg-charcoal text-[0.68rem] font-bold text-ivory">{initials}</span><span className="max-w-28 truncate text-xs font-semibold">{firstName}</span></Link>
          </div>
        </header>

        <main id="admin-main" tabIndex={-1} className="mx-auto w-full max-w-[1600px] min-w-0 flex-1 px-4 pt-6 pb-20 outline-none sm:px-6 sm:pt-8 lg:px-8 lg:pb-12">
          <motion.div key={pathname} initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: shouldReduceMotion ? 0 : 0.2, ease: "easeOut" }} className="min-w-0"><Outlet /></motion.div>
        </main>
      </div>

      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            <motion.div aria-hidden="true" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: shouldReduceMotion ? 0 : 0.18 }} onClick={() => setMobileMenuOpen(false)} className="fixed inset-0 z-40 bg-charcoal/45 lg:hidden" />
            <motion.div ref={drawerRef} role="dialog" aria-modal="true" aria-label="Admin console navigation drawer" initial={shouldReduceMotion ? false : { x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ type: "spring", bounce: 0, duration: shouldReduceMotion ? 0 : 0.28 }} className="fixed inset-y-0 left-0 z-50 flex w-[min(20rem,calc(100vw-3rem))] flex-col border-r border-charcoal/10 bg-[#FAFAF7] p-5 shadow-2xl lg:hidden">
              <div className="min-h-0 flex-1 overflow-y-auto">
                <div className="flex items-center justify-between border-b border-charcoal/10 pb-4"><Logo href="/admin" tone="dark" /><button type="button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation menu" className="rounded-lg p-1.5 text-charcoal/70 hover:bg-charcoal/5"><X aria-hidden="true" className="size-5" /></button></div>
                <nav aria-label="Mobile Navigation" className="mt-5"><AdminNavigationSections groups={groups} mobile settingsOpen={settingsOpen} onSettingsOpenChange={setSettingsOpen} onNavigate={() => setMobileMenuOpen(false)} /></nav>
              </div>
              <div className="border-t border-charcoal/10 pt-4">
                <Link to="/admin/account" className="mb-3 flex items-center gap-3 rounded-xl border border-charcoal/10 bg-white/80 p-3"><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-charcoal text-xs font-bold text-ivory">{initials}</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{user.full_name}</span><span className="block truncate text-[0.68rem] text-charcoal/60">{user.email}</span></span></Link>
                <button type="button" onClick={() => void handleSignOut()} className="flex w-full items-center justify-center gap-2 rounded-xl border border-charcoal/15 px-3 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50"><LogOut aria-hidden="true" className="size-3.5" /><span>Sign out</span></button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <nav aria-label="Mobile quick navigation" className="fixed inset-x-0 bottom-0 z-30 border-t border-charcoal/10 bg-[#FAFAF7]/95 px-1 pb-[env(safe-area-inset-bottom,0px)] backdrop-blur-md lg:hidden">
        <div className="flex h-16 items-center justify-around">
          {mobilePrimary.map((item) => {
            const Icon = adminNavigationIcon(item.to);
            const isActive = isPathActive(pathname, item);
            return (
              <Link key={item.to} to={item.to} aria-current={isActive ? "page" : undefined} className={`flex min-w-12 flex-col items-center justify-center gap-1 rounded-lg px-1.5 py-1.5 text-center transition-colors ${isActive ? "font-semibold text-charcoal" : "text-charcoal/60 hover:text-charcoal"}`}>
                <Icon aria-hidden="true" className="size-[18px]" /><span className="text-[0.6rem] tracking-tight">{item.shortLabel}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
