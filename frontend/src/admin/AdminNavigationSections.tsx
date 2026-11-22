import { NavLink, useLocation } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import type { AdminNavigationGroup, AdminNavigationItem } from "./adminNavigation";
import { adminNavigationIcon } from "./adminNavigationIcons";

interface AdminNavigationSectionsProps {
  groups: readonly AdminNavigationGroup[];
  collapsed?: boolean;
  mobile?: boolean;
  settingsOpen: boolean;
  onSettingsOpenChange: (open: boolean) => void;
  onNavigate?: () => void;
}

function isItemActive(pathname: string, item: AdminNavigationItem): boolean {
  return item.exact
    ? pathname === item.to || pathname === `${item.to}/overview`
    : pathname === item.to || pathname.startsWith(`${item.to}/`);
}

function itemClass(isActive: boolean, collapsed: boolean): string {
  return [
    "relative flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-colors",
    collapsed ? "justify-center px-2" : "px-3.5",
    isActive
      ? "bg-charcoal font-semibold text-ivory shadow-xs"
      : "text-charcoal/75 hover:bg-charcoal/5 hover:text-charcoal",
  ].join(" ");
}

function SettingsAccordion({
  item,
  isActive,
  collapsed,
  open,
  onToggle,
  onNavigate,
  contentId,
}: {
  item: AdminNavigationItem;
  isActive: boolean;
  collapsed: boolean;
  open: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  contentId: string;
}) {
  const Icon = adminNavigationIcon(item.to);
  return (
    <>
      <div className="flex items-center gap-1">
        <NavLink
          to={item.to}
          end
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          aria-current={isActive ? "page" : undefined}
          className={({ isActive: linkActive }) =>
            itemClass(linkActive || isActive, collapsed)
          }
        >
          {({ isActive: linkActive }) => (
            <>
              <Icon
                aria-hidden="true"
                className={`size-[18px] shrink-0 ${
                  linkActive || isActive ? "text-ivory" : "text-charcoal/60"
                }`}
              />
              <span className={collapsed ? "sr-only" : "truncate"}>{item.label}</span>
              {collapsed && (linkActive || isActive) && (
                <span aria-hidden="true" className="absolute top-1/2 right-1.5 size-1.5 -translate-y-1/2 rounded-full bg-sand" />
              )}
            </>
          )}
        </NavLink>
        {!collapsed && (
          <button
            type="button"
            aria-label={open ? "Hide settings sections" : "Show settings sections"}
            aria-expanded={open}
            aria-controls={contentId}
            onClick={onToggle}
            className="grid size-8 shrink-0 place-items-center rounded-lg text-charcoal/50 transition-colors hover:bg-charcoal/5 hover:text-charcoal"
          >
            <ChevronDown aria-hidden="true" className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        )}
      </div>
      {open && !collapsed && (
        <ul id={contentId} className="mt-1 ml-[1.65rem] space-y-1 border-l border-charcoal/10 pl-2.5">
          {item.children?.map((child) => {
            const ChildIcon = adminNavigationIcon(child.to);
            return (
              <li key={child.to}>
                <NavLink
                  to={child.to}
                  end
                  onClick={onNavigate}
                  className={({ isActive: childActive }) =>
                    `flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium transition-colors ${
                      childActive
                        ? "bg-charcoal/5 font-semibold text-charcoal"
                        : "text-charcoal/55 hover:bg-charcoal/5 hover:text-charcoal"
                    }`
                  }
                >
                  {({ isActive: childActive }) => (
                    <>
                      <ChildIcon
                        aria-hidden="true"
                        className={`size-3.5 shrink-0 ${childActive ? "text-charcoal" : "text-charcoal/45"}`}
                      />
                      <span className="truncate">{child.label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export function AdminNavigationSections({
  groups,
  collapsed = false,
  mobile = false,
  settingsOpen,
  onSettingsOpenChange,
  onNavigate,
}: AdminNavigationSectionsProps) {
  const { pathname } = useLocation();
  const contentId = mobile ? "mobile-settings-navigation" : "desktop-settings-navigation";

  return (
    <div className={mobile ? "space-y-5" : "space-y-4"}>
      {groups.map((group) => (
        <section key={group.label} aria-label={collapsed ? undefined : group.label}>
          {!collapsed && (
            <h2 className="mb-1.5 px-3 text-[0.6rem] font-semibold tracking-[0.17em] text-charcoal/45 uppercase">
              {group.label}
            </h2>
          )}
          <ul className="space-y-1">
            {group.items.map((item) => {
              const Icon = adminNavigationIcon(item.to);
              const isActive = isItemActive(pathname, item);
              const isSettingsAccordion =
                item.to === "/admin/settings" && (item.children?.length ?? 0) > 0;
              return (
                <li key={item.to}>
                  {isSettingsAccordion ? (
                    <SettingsAccordion
                      item={item}
                      isActive={isActive}
                      collapsed={collapsed}
                      open={settingsOpen}
                      onToggle={() => onSettingsOpenChange(!settingsOpen)}
                      onNavigate={onNavigate}
                      contentId={contentId}
                    />
                  ) : (
                    <NavLink
                      to={item.to}
                      end={item.exact}
                      onClick={onNavigate}
                      title={collapsed ? item.label : undefined}
                      aria-current={isActive ? "page" : undefined}
                      className={({ isActive: linkActive }) =>
                        itemClass(linkActive, collapsed)
                      }
                    >
                      {({ isActive: linkActive }) => (
                        <>
                          <Icon
                            aria-hidden="true"
                            className={`size-[18px] shrink-0 ${
                              linkActive ? "text-ivory" : "text-charcoal/60"
                            }`}
                          />
                          <span className={collapsed ? "sr-only" : "truncate"}>{item.label}</span>
                          {collapsed && linkActive && (
                            <span aria-hidden="true" className="absolute top-1/2 right-1.5 size-1.5 -translate-y-1/2 rounded-full bg-sand" />
                          )}
                        </>
                      )}
                    </NavLink>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
