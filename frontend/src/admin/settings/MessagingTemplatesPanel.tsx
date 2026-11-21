import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  LoaderCircle,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { deleteMessageTemplate, updateMessageTemplate } from "../messagingApi";
import { errorMessage } from "../../shared/apiRequest";
import type {
  MessageTemplateItem,
  MessageTemplateListResponse,
} from "../messagingModel";
import { MessageTemplateModal } from "./MessageTemplateModal";
import {
  channelBadgeClasses,
  channelLabel,
  messagingPrimaryButton,
} from "./messagingUi";

interface MessagingTemplatesPanelProps {
  data: MessageTemplateListResponse | undefined;
  isLoading: boolean;
  onNotice: (tone: "error" | "success", message: string) => void;
}

export function MessagingTemplatesPanel({
  data,
  isLoading,
  onNotice,
}: MessagingTemplatesPanelProps) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<MessageTemplateItem | "new" | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const templates = data?.items ?? [];

  const invalidateMessaging = async () => {
    await queryClient.invalidateQueries({ queryKey: ["messaging", "templates"] });
    await queryClient.invalidateQueries({ queryKey: ["messaging", "rules"] });
  };

  const toggleTemplate = async (template: MessageTemplateItem) => {
    setPendingId(template.id);
    try {
      await updateMessageTemplate(template.id, { is_active: !template.is_active });
      await invalidateMessaging();
      onNotice("success", `${template.name} ${template.is_active ? "disabled" : "enabled"}.`);
    } catch (error: unknown) {
      onNotice("error", errorMessage(error, "Failed to update template status."));
    } finally {
      setPendingId(null);
    }
  };

  const removeTemplate = async (template: MessageTemplateItem) => {
    const confirmed = window.confirm(
      `Delete “${template.name}”? This cannot be undone. Templates used by trigger rules cannot be deleted.`,
    );
    if (!confirmed) return;

    setPendingId(template.id);
    try {
      await deleteMessageTemplate(template.id);
      await invalidateMessaging();
      onNotice("success", `${template.name} deleted.`);
    } catch (error: unknown) {
      onNotice("error", errorMessage(error, "Failed to delete template."));
    } finally {
      setPendingId(null);
    }
  };

  return (
    <section aria-labelledby="messaging-templates-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="messaging-templates-heading" className="text-sm font-semibold text-charcoal">
            Message templates
          </h3>
          <p className="mt-1 text-xs leading-5 text-charcoal/55">
            Reusable channel-specific content with dynamic merge variables.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing("new")}
          className={messagingPrimaryButton}
        >
          <Plus aria-hidden="true" className="size-3.5" />
          New template
        </button>
      </div>

      {isLoading ? (
        <div className="flex min-h-40 items-center justify-center gap-2 text-xs text-charcoal/50">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Loading templates…
        </div>
      ) : templates.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-charcoal/15 bg-charcoal/[0.025] px-5 py-10 text-center">
          <FileText aria-hidden="true" className="mx-auto size-5 text-charcoal/35" />
          <p className="mt-2 text-xs font-semibold text-charcoal">No message templates yet</p>
          <p className="mt-1 text-[11px] text-charcoal/50">
            Create a template to start sending automated WhatsApp, SMS, or email messages.
          </p>
        </div>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {templates.map((template) => (
            <article
              key={template.id}
              className="flex min-w-0 flex-col rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs transition-colors hover:border-charcoal/20 sm:p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="truncate text-sm font-semibold text-charcoal">{template.name}</h4>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${channelBadgeClasses(template.channel)}`}>
                      {channelLabel(template.channel)}
                    </span>
                    <span className="rounded-md border border-charcoal/10 bg-charcoal/5 px-2 py-0.5 text-[10px] font-semibold text-charcoal/55 uppercase">
                      {template.language}
                    </span>
                    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${template.is_active ? "bg-emerald-50 text-emerald-800" : "bg-charcoal/10 text-charcoal/50"}`}>
                      {template.is_active ? "Active" : "Disabled"}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={template.is_active}
                  aria-label={`${template.is_active ? "Disable" : "Enable"} ${template.name}`}
                  disabled={pendingId === template.id}
                  onClick={() => void toggleTemplate(template)}
                  className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${template.is_active ? "bg-forest" : "bg-charcoal/20"}`}
                >
                    <span
                      className={`absolute top-1 size-4 rounded-full bg-white shadow-sm transition-transform ${template.is_active ? "left-6" : "left-1"}`}
                    />
                </button>
              </div>

              <p className="mt-4 line-clamp-4 rounded-xl bg-charcoal/[0.035] p-3 text-xs leading-5 whitespace-pre-wrap text-charcoal/75">
                {template.body}
              </p>

              {template.variables.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1">
                  {template.variables.map((variable, index) => (
                    <span
                      key={`${variable}-${index}`}
                      className="rounded-md border border-charcoal/10 px-1.5 py-0.5 font-mono text-[10px] text-charcoal/55"
                    >
                      {`{${variable}}`}
                    </span>
                  ))}
                </div>
              ) : null}

              {template.provider_template_name ? (
                <p className="mt-3 truncate text-[10px] text-charcoal/45">
                  Provider template: <span className="font-mono">{template.provider_template_name}</span>
                </p>
              ) : null}

              <div className="mt-4 flex items-center justify-end gap-2 border-t border-charcoal/10 pt-3">
                <button
                  type="button"
                  onClick={() => setEditing(template)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-charcoal/15 px-2.5 py-1.5 text-[11px] font-semibold text-charcoal/70 hover:bg-charcoal/5"
                >
                  <Pencil aria-hidden="true" className="size-3" />
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => void removeTemplate(template)}
                  disabled={pendingId === template.id}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-clay/20 px-2.5 py-1.5 text-[11px] font-semibold text-clay hover:bg-clay-soft disabled:opacity-50"
                >
                  {pendingId === template.id ? (
                    <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />
                  ) : (
                    <Trash2 aria-hidden="true" className="size-3" />
                  )}
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {editing ? (
        <MessageTemplateModal
          template={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (message) => {
            setEditing(null);
            await invalidateMessaging();
            onNotice("success", message);
          }}
        />
      ) : null}
    </section>
  );
}
