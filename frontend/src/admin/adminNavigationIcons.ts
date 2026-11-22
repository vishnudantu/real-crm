import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Bell,
  BookCheck,
  Bot,
  Building2,
  CalendarDays,
  CircleUserRound,
  Code2,
  Inbox,
  Languages,
  LayoutDashboard,
  LayoutGrid,
  ListChecks,
  MessageSquare,
  Palette,
  Plug,
  Scale,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";

const ICONS_BY_PATH: Readonly<Record<string, LucideIcon>> = {
  "/admin": LayoutDashboard,
  "/admin/inbox": Inbox,
  "/admin/notifications": Bell,
  "/admin/projects": Building2,
  "/admin/inventory": LayoutGrid,
  "/admin/inventory/units": ListChecks,
  "/admin/visits": CalendarDays,
  "/admin/users": Users,
  "/admin/analytics": BarChart3,
  "/admin/sales-bookings": BookCheck,
  "/admin/channels": Plug,
  "/admin/settings": Settings,
  "/admin/audit-logs": ShieldCheck,
  "/admin/account": CircleUserRound,
  "/admin/settings/branding": Palette,
  "/admin/settings/ai": Bot,
  "/admin/settings/languages": Languages,
  "/admin/settings/reminders": Bell,
  "/admin/settings/assignment": Scale,
  "/admin/settings/messaging": MessageSquare,
  "/admin/settings/widget": Code2,
};

export function adminNavigationIcon(path: string): LucideIcon {
  return ICONS_BY_PATH[path] ?? Settings;
}
