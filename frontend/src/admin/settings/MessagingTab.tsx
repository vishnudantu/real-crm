import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Inbox,
  RotateCw,
  Send,
  Zap,
} from "lucide-react";
import { fetchMessageTemplates, fetchTriggerRules } from "../messagingApi";
import { MessagingTemplatesPanel } from "./MessagingTemplatesPanel";
import { MessagingRulesPanel } from "./MessagingRulesPanel";
import { MessagingDeliveriesPanel } from "./MessagingDeliveriesPanel";
import { SendTestModal } from "./SendTestModal";
import { messagingSecondaryButton } from "./messagingUi";

type MessagingView = "templates" | "rules" | "deliveries";

interface Notice {
  tone: "error" | "success";
  message: string;
}

export function MessagingTab() {
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState<MessagingView>("templates");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [testModalOpen, setTestModalOpen] = useState(false);

  const templatesQuery = useQuery({
    queryKey: ["messaging", "templates"],
    queryFn: fetchMessageTemplates,
  });
  const rulesQuery = useQuery({
    queryKey: ["messaging", "rules"],
    queryFn: fetchTriggerRules,
  });
  const templates = templatesQuery.data?.items ?? [];

  const showNotice = (tone: Notice["tone"], message: string) => {
    setNotice({ tone, message });
  };

  const refreshConfiguration = async () => {
    setNotice(null);
    await Promise.all([templatesQuery.refetch(), rulesQuery.refetch()]);
  };

  const views: { id: MessagingView; label: string; icon: typeof FileText }[] = [
    { id: "templates", label: "Templates", icon: FileText },
    { id: "rules", label: "Automation rules", icon: Zap },
    { id: "deliveries", label: "Delivery log", icon: Inbox },
  ];

  const loadError = templatesQuery.error ?? rulesQuery.error;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold tracking-tight text-charcoal">
            Outbound messaging
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-charcoal/55">
            Configure WhatsApp, SMS, and email templates, automate event-driven
            delivery, and inspect message outcomes.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void refreshConfiguration()}
            disabled={templatesQuery.isFetching || rulesQuery.isFetching}
            className={messagingSecondaryButton}
          >
            <RotateCw
              aria-hidden="true"
              className={`size-3.5 ${templatesQuery.isFetching || rulesQuery.isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => {
              setNotice(null);
              setTestModalOpen(true);
            }}
            className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl bg-charcoal px-3.5 py-2 text-[11px] font-semibold text-white shadow-xs transition-colors hover:bg-charcoal/90"
          >
            <Send aria-hidden="true" className="size-3.5" />
            Send test
          </button>
        </div>
      </div>

      {notice ? (
        <div
          role={notice.tone === "error" ? "alert" : "status"}
          className={`flex items-start gap-2 rounded-xl border px-3.5 py-3 text-xs leading-5 ${
            notice.tone === "error"
              ? "border-clay/25 bg-clay-soft text-clay"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          {notice.tone === "error" ? (
            <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          ) : (
            <CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          )}
          <span>{notice.message}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="ml-auto text-[10px] font-semibold opacity-70 hover:opacity-100"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      {loadError ? (
        <div role="alert" className="rounded-xl border border-clay/25 bg-clay-soft p-3.5 text-xs text-clay">
          {loadError instanceof Error
            ? loadError.message
            : "Messaging configuration could not be loaded."}
        </div>
      ) : null}

      <div className="flex w-full gap-1 rounded-2xl border border-charcoal/10 bg-charcoal/[0.04] p-1 sm:w-fit">
        {views.map((view) => {
          const Icon = view.icon;
          return (
            <button
              key={view.id}
              type="button"
              onClick={() => {
                setActiveView(view.id);
                setNotice(null);
              }}
              aria-pressed={activeView === view.id}
              className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-[11px] font-semibold whitespace-nowrap transition-colors sm:flex-none ${
                activeView === view.id
                  ? "bg-white text-charcoal shadow-xs"
                  : "text-charcoal/55 hover:text-charcoal"
              }`}
            >
              <Icon aria-hidden="true" className="size-3.5" />
              {view.label}
            </button>
          );
        })}
      </div>

      <div className="min-w-0">
        {activeView === "templates" ? (
          <MessagingTemplatesPanel
            data={templatesQuery.data}
            isLoading={templatesQuery.isLoading}
            onNotice={showNotice}
          />
        ) : null}
        {activeView === "rules" ? (
          <MessagingRulesPanel
            data={rulesQuery.data}
            templates={templates}
            isLoading={rulesQuery.isLoading || templatesQuery.isLoading}
            onNotice={showNotice}
          />
        ) : null}
        {activeView === "deliveries" ? <MessagingDeliveriesPanel /> : null}
      </div>

      {testModalOpen ? (
        <SendTestModal
          templates={templates}
          onClose={() => setTestModalOpen(false)}
          onSent={async (message) => {
            setTestModalOpen(false);
            setActiveView("deliveries");
            showNotice("success", message);
            await queryClient.invalidateQueries({ queryKey: ["messaging", "deliveries"] });
          }}
        />
      ) : null}
    </div>
  );
}
