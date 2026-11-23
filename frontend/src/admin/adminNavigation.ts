export interface AdminNavigationItem {
  label: string;
  shortLabel: string;
  to: string;
  exact?: boolean;
  children?: readonly AdminNavigationItem[];
}

export interface AdminNavigationGroup {
  label: string;
  items: readonly AdminNavigationItem[];
}

interface NavigationDefinition extends AdminNavigationItem {
  feature?: string;
  children?: readonly NavigationDefinition[];
}

interface NavigationGroupDefinition {
  label: string;
  items: readonly NavigationDefinition[];
}

const SETTINGS_CHILDREN: readonly NavigationDefinition[] = [
  { label: "Branding", shortLabel: "Branding", to: "/admin/settings/branding" },
  { label: "Roles", shortLabel: "Roles", to: "/admin/settings/roles" },
  { label: "AI Assistant", shortLabel: "AI", to: "/admin/settings/ai" },
  { label: "AI Providers", shortLabel: "AI Providers", to: "/admin/settings/ai-providers" },
  { label: "Languages", shortLabel: "Languages", to: "/admin/settings/languages" },
  { label: "Reminders", shortLabel: "Reminders", to: "/admin/settings/reminders" },
  { label: "Lead Assignment", shortLabel: "Assignment", to: "/admin/settings/assignment" },
  { label: "Messaging", shortLabel: "Messaging", to: "/admin/settings/messaging" },
  { label: "Website Widget", shortLabel: "Widget", to: "/admin/settings/widget", feature: "omnichannel_inbox" },
];

const NAVIGATION_DEFINITIONS: readonly NavigationGroupDefinition[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", shortLabel: "Home", to: "/admin", exact: true },
      { label: "Sales War Room", shortLabel: "War Room", to: "/admin/war-room" },
    ],
  },
  {
    label: "Engage",
    items: [
      { label: "Omnichannel Inbox", shortLabel: "Inbox", to: "/admin/inbox", feature: "omnichannel_inbox" },
      { label: "Notifications", shortLabel: "Alerts", to: "/admin/notifications" },
    ],
  },
  {
    label: "Catalog",
    items: [
      { label: "Projects & Fact Sheets", shortLabel: "Projects", to: "/admin/projects" },
      { label: "Site Visits & Slots", shortLabel: "Visits", to: "/admin/visits" },
      { label: "Construction Progress", shortLabel: "Construction", to: "/admin/construction" },
    ],
  },
  {
    label: "Customers",
    items: [
      { label: "Customer Directory", shortLabel: "Directory", to: "/admin/customers" },
      { label: "Opportunity Pipeline", shortLabel: "Opportunities", to: "/admin/opportunities" },
      { label: "Channel Partners", shortLabel: "Partners", to: "/admin/brokers" },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Approvals", shortLabel: "Approvals", to: "/admin/approvals" },
      { label: "Service Desk", shortLabel: "Service Desk", to: "/admin/service-desk" },
      { label: "Call Intelligence", shortLabel: "Call Intel", to: "/admin/call-intelligence" },
    ],
  },
  {
    label: "Property",
    items: [
      { label: "Inventory Map", shortLabel: "Map", to: "/admin/inventory", exact: true },
      { label: "Units & Import", shortLabel: "Units", to: "/admin/inventory/units" },
    ],
  },
  {
    label: "Team",
    items: [
      { label: "Team Chat", shortLabel: "Team Chat", to: "/admin/teamchat" },
      { label: "User Management", shortLabel: "Users", to: "/admin/users" },
    ],
  },
  {
    label: "Revenue",
    items: [
      { label: "Analytics & Reports", shortLabel: "Analytics", to: "/admin/analytics", feature: "analytics" },
      { label: "Sales Bookings", shortLabel: "Bookings", to: "/admin/sales-bookings", feature: "post_sales" },
      { label: "Documents", shortLabel: "Documents", to: "/admin/documents" },
      { label: "Bank Reconciliation", shortLabel: "Reconciliation", to: "/admin/reconciliation" },
    ],
  },
  {
    label: "Integrate",
    items: [
      { label: "Channels & Widget", shortLabel: "Channels", to: "/admin/channels", feature: "omnichannel_inbox" },
      { label: "Ad Connections", shortLabel: "Connections", to: "/admin/integrations", feature: "connectors" },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Settings", shortLabel: "Settings", to: "/admin/settings", children: SETTINGS_CHILDREN },
      { label: "Audit Trail", shortLabel: "Audit", to: "/admin/audit-logs" },
      { label: "My Account", shortLabel: "Account", to: "/admin/account" },
    ],
  },
];

const SETTINGS_TAB_BY_SEGMENT: Readonly<Record<string, string>> = {
  branding: "branding",
  roles: "roles",
  ai: "ai_assistant",
  languages: "languages",
  reminders: "reminders",
  assignment: "lead_assignment",
  messaging: "messaging",
  templates: "templates",
  widget: "widget",
};

function visibleItem(
  item: NavigationDefinition,
  features: Readonly<Record<string, boolean>>,
): AdminNavigationItem | null {
  if (item.feature && !features[item.feature]) return null;

  const children = item.children
    ?.map((child) => visibleItem(child, features))
    .filter((child): child is AdminNavigationItem => child !== null);

  return {
    label: item.label,
    shortLabel: item.shortLabel,
    to: item.to,
    ...(item.exact ? { exact: true } : {}),
    ...(children ? { children } : {}),
  };
}

export function buildAdminNav(
  features: Readonly<Record<string, boolean>>,
): AdminNavigationGroup[] {
  return NAVIGATION_DEFINITIONS.map((group) => ({
    label: group.label,
    items: group.items
      .map((item) => visibleItem(item, features))
      .filter((item): item is AdminNavigationItem => item !== null),
  })).filter((group) => group.items.length > 0);
}

export function buildManagerNav(): AdminNavigationGroup[] {
  return [{ label: "Overview", items: [{ label: "Sales War Room", shortLabel: "War Room", to: "/admin/war-room" }] }];
}

export function buildAdminMobileNav(
  features: Readonly<Record<string, boolean>>,
): AdminNavigationItem[] {
  const items = buildAdminNav(features).flatMap((group) => group.items);
  const inbox = items.find((item) => item.to === "/admin/inbox");
  const destinations = inbox
    ? ["/admin", "/admin/inbox", "/admin/projects", "/admin/visits", "/admin/account"]
    : ["/admin", "/admin/projects", "/admin/visits", "/admin/notifications", "/admin/account"];

  return destinations
    .map((destination) => items.find((item) => item.to === destination))
    .filter((item): item is AdminNavigationItem => item !== undefined)
    .slice(0, 5);
}

export function resolveSettingsTab(pathname: string): string {
  const match = /^\/admin\/settings(?:\/([^/]+))?\/?$/.exec(pathname);
  const segment = match?.[1];
  return (segment && SETTINGS_TAB_BY_SEGMENT[segment]) || "branding";
}
