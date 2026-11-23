import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, useLocation } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  Bell,
  Bot,
  CheckCircle2,
  Code2,
  FileText,
  Languages,
  LoaderCircle,
  Megaphone,
  MessageSquare,
  Palette,
  Scale,
  Settings,
  Shield,
} from "lucide-react";
import { normalizeBranding, resolveTenantSlug } from "../tenant/branding";
import { publicBrandingQueryKey } from "../tenant/TenantProvider";
import { updateTenantBranding } from "../tenant/api";
import type { UpdateTenantBrandingPayload } from "../tenant/types";
import { BrandingSettingsTab } from "./settings/BrandingSettingsTab";
import { AIAssistantSettingsTab } from "./settings/AIAssistantSettingsTab";
import { LanguageSettingsPanel } from "./settings/LanguageSettingsPanel";
import { WebsiteWidgetInstaller } from "../omnichannel/WebsiteWidgetInstaller";
import type {
  AllSystemSettingsResponse,
  AuditLogListResponse,
  BroadcastNotificationPayload,
  NotificationTemplateItem,
  SystemNotificationListResponse,
  UpdateAIAssistantSettingsPayload,
  UpdateLanguageSettingsPayload,
  UpdateLeadAssignmentSettingsPayload,
  UpdateNotificationTemplatePayload,
  UpdateReminderSettingsPayload,
} from "./settingsModel";
import {
  broadcastSystemNotification,
  fetchAuditLogs,
  fetchNotificationTemplates,
  fetchSystemNotifications,
  fetchSystemSettings,
  resetNotificationTemplate,
  triggerRemindersScan,
  updateAIAssistantSettings,
  updateLanguageSettings,
  updateLeadAssignmentSettings,
  updateNotificationTemplate,
  updateReminderSettings,
} from "./api";
import { RemindersConfigTab } from "./settings/RemindersConfigTab";
import { SystemNotificationsTab } from "./settings/SystemNotificationsTab";
import { NotificationTemplatesTab } from "./settings/NotificationTemplatesTab";
import { LeadAssignmentTab } from "./settings/LeadAssignmentTab";
import { AuditLogsTab } from "./settings/AuditLogsTab";
import { resolveSettingsTab } from "./adminNavigation";
import { useFeatures } from "../features/FeaturesProvider";
import { errorMessage } from "../shared/apiRequest";

const MessagingTab = lazy(() => import("./settings/MessagingTab").then((module) => ({ default: module.MessagingTab })));

export type SettingsTab =
  | "reminders"
  | "notifications"
  | "templates"
  | "messaging"
  | "ai_assistant"
  | "languages"
  | "lead_assignment"
  | "audit_logs"
  | "branding"
  | "widget";

export interface SystemSettingsPageProps {
  initialTab?: SettingsTab;
}

const VALID_TABS = new Set<SettingsTab>([
  "reminders", "notifications", "templates", "messaging", "ai_assistant",
  "languages", "lead_assignment", "audit_logs", "branding", "widget",
]);

interface SettingsTabDefinition {
  id: SettingsTab;
  label: string;
  to: string;
  icon: LucideIcon;
  feature?: string;
}

const SETTINGS_TABS: readonly SettingsTabDefinition[] = [
  { id: "branding", label: "Branding", to: "/admin/settings/branding", icon: Palette },
  { id: "ai_assistant", label: "AI Assistant", to: "/admin/settings/ai", icon: Bot },
  { id: "languages", label: "Languages", to: "/admin/settings/languages", icon: Languages },
  { id: "reminders", label: "Reminders & Alerts", to: "/admin/settings/reminders", icon: Bell },
  { id: "lead_assignment", label: "Lead Assignment", to: "/admin/settings/assignment", icon: Scale },
  { id: "messaging", label: "Messaging", to: "/admin/settings/messaging", icon: MessageSquare },
  { id: "widget", label: "Website Widget", to: "/admin/settings/widget", icon: Code2, feature: "omnichannel_inbox" },
  { id: "notifications", label: "System Notifications", to: "/admin/notifications", icon: Megaphone },
  { id: "templates", label: "Notification Templates", to: "/admin/settings/templates", icon: FileText },
  { id: "audit_logs", label: "Audit Trail", to: "/admin/audit-logs", icon: Shield },
];

function tabFromPath(
  pathname: string,
  search: string,
  initialTab?: SettingsTab,
): SettingsTab {
  if (initialTab && VALID_TABS.has(initialTab)) return initialTab;
  if (pathname === "/admin/settings") {
    // Legacy deep links used ?tab=<id>; path segments are the canonical form.
    const queryTab = new URLSearchParams(search).get("tab");
    if (queryTab && VALID_TABS.has(queryTab as SettingsTab)) {
      return queryTab as SettingsTab;
    }
  }
  const tab = resolveSettingsTab(pathname);
  return VALID_TABS.has(tab as SettingsTab) ? (tab as SettingsTab) : "branding";
}

export function SystemSettingsPage({ initialTab }: SystemSettingsPageProps = {}) {
  const { pathname, search } = useLocation();
  const { enabled } = useFeatures();
  const queryClient = useQueryClient();
  const activeTab = tabFromPath(pathname, search, initialTab);
  const [settings, setSettings] = useState<AllSystemSettingsResponse | null>(null);
  const [templates, setTemplates] = useState<NotificationTemplateItem[]>([]);
  const [notificationsData, setNotificationsData] = useState<SystemNotificationListResponse | null>(null);
  const [logsData, setLogsData] = useState<AuditLogListResponse | null>(null);
  const [notifPage, setNotifPage] = useState(1);
  const [notifType, setNotifType] = useState("ALL");
  const [notifSearch, setNotifSearch] = useState("");
  const [auditPage, setAuditPage] = useState(1);
  const [auditAction, setAuditAction] = useState("ALL");
  const [auditSearch, setAuditSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const loadSettingsData = useCallback(async () => {
    try {
      setSettings(await fetchSystemSettings());
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to load system settings."));
    }
  }, []);

  const loadTemplatesData = useCallback(async () => {
    try {
      setTemplates((await fetchNotificationTemplates()).items);
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to load notification templates."));
    }
  }, []);

  const loadNotificationsData = useCallback(async () => {
    try {
      setNotificationsData(await fetchSystemNotifications({
        page: notifPage,
        pageSize: 15,
        type: notifType !== "ALL" ? notifType : undefined,
        search: notifSearch || undefined,
      }));
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to load notifications."));
    }
  }, [notifPage, notifType, notifSearch]);

  const loadAuditLogsData = useCallback(async () => {
    try {
      setLogsData(await fetchAuditLogs({
        page: auditPage,
        pageSize: 15,
        action: auditAction !== "ALL" ? auditAction : undefined,
        search: auditSearch || undefined,
      }));
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to load audit logs."));
    }
  }, [auditPage, auditAction, auditSearch]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const requests: Promise<void>[] = [];
      if (activeTab === "widget") {
        setLoading(false);
        return;
      }
      if (["ai_assistant", "languages", "reminders", "lead_assignment"].includes(activeTab)) requests.push(loadSettingsData());
      if (activeTab === "templates") requests.push(loadTemplatesData());
      if (activeTab === "notifications") requests.push(loadNotificationsData());
      if (activeTab === "audit_logs") requests.push(loadAuditLogsData());
      await Promise.allSettled(requests);
      setLoading(false);
    };
    void load();
  }, [activeTab, loadSettingsData, loadTemplatesData, loadNotificationsData, loadAuditLogsData]);

  const save = async (operation: () => Promise<void>) => {
    setIsSaving(true);
    setError(null);
    try {
      await operation();
      void loadAuditLogsData();
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Your settings could not be saved."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateReminders = (payload: UpdateReminderSettingsPayload) => save(async () => {
    const updated = await updateReminderSettings(payload);
    setSettings((current) => current ? { ...current, reminders: updated } : current);
    setToast("Site visit reminder configuration updated successfully.");
  });

  const handleTriggerReminders = async () => {
    setIsTriggering(true);
    try {
      const result = await triggerRemindersScan();
      setToast(`Reminder scan complete. Dispatched ${result.dispatched_count} notifications.`);
      await loadSettingsData();
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to trigger reminders scan."));
    } finally {
      setIsTriggering(false);
    }
  };

  const handleUpdateAI = (payload: UpdateAIAssistantSettingsPayload) => save(async () => {
    const updated = await updateAIAssistantSettings(payload);
    setSettings((current) => current ? { ...current, ai_assistant: updated } : current);
    setToast("AI Assistant grounding and generation settings updated.");
  });

  const handleUpdateLanguages = (payload: UpdateLanguageSettingsPayload) => save(async () => {
    const updated = await updateLanguageSettings(payload);
    setSettings((current) => current ? { ...current, languages: updated } : current);
    setToast("Multilingual support languages updated successfully.");
  });

  const handleUpdateLeadAssignment = (payload: UpdateLeadAssignmentSettingsPayload) => save(async () => {
    const updated = await updateLeadAssignmentSettings(payload);
    setSettings((current) => current ? { ...current, lead_assignment: updated } : current);
    setToast("Lead routing and assignment strategy updated.");
  });

  const handleUpdateTemplate = (templateId: string, payload: UpdateNotificationTemplatePayload) => save(async () => {
    await updateNotificationTemplate(templateId, payload);
    await loadTemplatesData();
    setToast("Notification template updated successfully.");
  });

  const handleResetTemplate = (templateId: string) => save(async () => {
    await resetNotificationTemplate(templateId);
    await loadTemplatesData();
    setToast("Notification template restored to system default wording.");
  });

  const handleBroadcast = async (payload: BroadcastNotificationPayload) => {
    setIsBroadcasting(true);
    setError(null);
    try {
      setToast((await broadcastSystemNotification(payload)).message);
      await loadNotificationsData();
    } catch (reason: unknown) {
      setError(errorMessage(reason, "The notification could not be broadcast."));
    } finally {
      setIsBroadcasting(false);
    }
  };

  const handleUpdateBranding = async (payload: UpdateTenantBrandingPayload) => {
    setIsSaving(true);
    try {
      const slug = resolveTenantSlug();
      const updated = normalizeBranding(await updateTenantBranding(payload), undefined, slug);
      queryClient.setQueryData(publicBrandingQueryKey(slug), updated);
      queryClient.setQueryData(["tenant", "settings", slug], updated);
      setToast("Tenant branding settings updated successfully.");
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Failed to update tenant branding."));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      {toast && <div role="status" className="fixed right-6 bottom-20 z-50 flex items-center gap-2 rounded-xl bg-charcoal px-4 py-3 text-xs font-semibold text-white shadow-xl lg:bottom-6"><CheckCircle2 aria-hidden="true" className="size-4 text-emerald-400" /><span>{toast}</span></div>}
      <header><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-charcoal text-ivory"><Settings aria-hidden="true" className="size-4" /></span><h1 className="text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">Workspace Settings</h1></div><p className="mt-2 max-w-3xl text-sm leading-6 text-charcoal/60">Manage branding, customer engagement, team routing and website channels from one place.</p></header>
      {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-800"><AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-red-600" /><span>{error}</span></div>}

      <nav aria-label="Settings sections" className="flex flex-wrap items-center gap-1.5 rounded-2xl border border-charcoal/10 bg-charcoal/5 p-1.5 text-xs font-semibold">
        {SETTINGS_TABS.filter((tab) => !tab.feature || enabled(tab.feature)).map((tab) => {
          const Icon = tab.icon;
          return <NavLink key={tab.id} to={tab.to} end className={activeTab === tab.id ? "inline-flex items-center gap-2 rounded-xl bg-white px-3.5 py-2 text-charcoal shadow-xs" : "inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-charcoal/60 transition-colors hover:bg-white/60 hover:text-charcoal"}><Icon aria-hidden="true" className="size-3.5" /><span>{tab.label}</span></NavLink>;
        })}
        <NavLink to="/admin/settings/ai-providers" className="inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-charcoal/60 transition-colors hover:bg-white/60 hover:text-charcoal"><Bot aria-hidden="true" className="size-3.5" /><span>AI Providers</span></NavLink>
      </nav>

      {loading ? (
        <div role="status" className="flex h-56 w-full items-center justify-center gap-2 text-xs text-charcoal/50"><LoaderCircle aria-hidden="true" className="size-5 animate-spin" />Loading settings…</div>
      ) : (
        <div>
          {activeTab === "branding" && <BrandingSettingsTab isSaving={isSaving} onUpdate={handleUpdateBranding} />}
          {activeTab === "widget" && <WebsiteWidgetInstaller />}
          {activeTab === "reminders" && settings && <RemindersConfigTab settings={settings.reminders} onUpdate={handleUpdateReminders} onTriggerScan={handleTriggerReminders} isSaving={isSaving} isTriggering={isTriggering} />}
          {activeTab === "ai_assistant" && settings && <AIAssistantSettingsTab aiSettings={settings.ai_assistant} onUpdateAI={handleUpdateAI} isSaving={isSaving} />}
          {activeTab === "languages" && settings && <LanguageSettingsPanel langSettings={settings.languages} onUpdateLanguages={handleUpdateLanguages} isSaving={isSaving} />}
          {activeTab === "lead_assignment" && settings && <LeadAssignmentTab settings={settings.lead_assignment} onUpdate={handleUpdateLeadAssignment} isSaving={isSaving} />}
          {activeTab === "messaging" && <Suspense fallback={<div className="flex h-56 items-center justify-center gap-2 text-xs text-charcoal/50"><LoaderCircle aria-hidden="true" className="size-4 animate-spin" />Loading messaging configuration…</div>}><MessagingTab /></Suspense>}
          {activeTab === "notifications" && <SystemNotificationsTab notificationsData={notificationsData} loading={false} page={notifPage} onPageChange={setNotifPage} typeFilter={notifType} onTypeFilterChange={(value) => { setNotifType(value); setNotifPage(1); }} search={notifSearch} onSearchChange={(value) => { setNotifSearch(value); setNotifPage(1); }} onBroadcast={handleBroadcast} isBroadcasting={isBroadcasting} />}
          {activeTab === "templates" && <NotificationTemplatesTab templates={templates} loading={false} onUpdateTemplate={handleUpdateTemplate} onResetTemplate={handleResetTemplate} isSaving={isSaving} />}
          {activeTab === "audit_logs" && <AuditLogsTab logsData={logsData} loading={false} page={auditPage} onPageChange={setAuditPage} actionFilter={auditAction} onActionFilterChange={(value) => { setAuditAction(value); setAuditPage(1); }} search={auditSearch} onSearchChange={(value) => { setAuditSearch(value); setAuditPage(1); }} />}
        </div>
      )}
    </div>
  );
}
