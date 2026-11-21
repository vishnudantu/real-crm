import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  LoaderCircle,
  Pencil,
  Plus,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import {
  createTriggerRule,
  deleteTriggerRule,
  updateTriggerRule,
} from "../messagingApi";
import { errorMessage } from "../../shared/apiRequest";
import type {
  MessageChannel,
  MessageTemplateItem,
  TriggerRuleItem,
  TriggerRuleListResponse,
} from "../messagingModel";
import {
  CHANNELS,
  KNOWN_MESSAGING_EVENTS,
  channelBadgeClasses,
  channelLabel,
  messagingInputClasses,
  messagingLabelClasses,
  messagingPrimaryButton,
  messagingSecondaryButton,
} from "./messagingUi";

const ruleSchema = z.object({
  event: z
    .string()
    .trim()
    .min(1, "Enter an event name.")
    .max(64)
    .regex(/^[a-z0-9_.]+$/, "Use lowercase letters, numbers, dots, and underscores."),
  channel: z.enum(["WHATSAPP", "SMS", "EMAIL"]),
  templateId: z.string().min(1, "Select a template."),
  delayMinutes: z
    .number()
    .int("Use whole minutes.")
    .min(0, "Delay cannot be negative.")
    .max(10080, "Delay cannot exceed 7 days."),
  enabled: z.boolean(),
});

type RuleFormValues = z.infer<typeof ruleSchema>;

interface MessagingRulesPanelProps {
  data: TriggerRuleListResponse | undefined;
  templates: MessageTemplateItem[];
  isLoading: boolean;
  onNotice: (tone: "error" | "success", message: string) => void;
}

export function MessagingRulesPanel({
  data,
  templates,
  isLoading,
  onNotice,
}: MessagingRulesPanelProps) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<TriggerRuleItem | "new" | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const rules = data?.items ?? [];

  const invalidateRules = async () => {
    await queryClient.invalidateQueries({ queryKey: ["messaging", "rules"] });
  };

  const toggleRule = async (rule: TriggerRuleItem) => {
    setPendingId(rule.id);
    try {
      await updateTriggerRule(rule.id, { enabled: !rule.enabled });
      await invalidateRules();
      onNotice("success", `Rule for ${rule.event} ${rule.enabled ? "disabled" : "enabled"}.`);
    } catch (error: unknown) {
      onNotice("error", errorMessage(error, "Failed to update trigger rule."));
    } finally {
      setPendingId(null);
    }
  };

  const removeRule = async (rule: TriggerRuleItem) => {
    if (!window.confirm(`Delete the trigger rule for “${rule.event}”?`)) return;
    setPendingId(rule.id);
    try {
      await deleteTriggerRule(rule.id);
      await invalidateRules();
      onNotice("success", `Trigger rule for ${rule.event} deleted.`);
    } catch (error: unknown) {
      onNotice("error", errorMessage(error, "Failed to delete trigger rule."));
    } finally {
      setPendingId(null);
    }
  };

  return (
    <section aria-labelledby="messaging-rules-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="messaging-rules-heading" className="text-sm font-semibold text-charcoal">
            Automation rules
          </h3>
          <p className="mt-1 text-xs leading-5 text-charcoal/55">
            Send a template automatically when a business event occurs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (templates.length === 0) {
              onNotice("error", "Create a message template before adding a trigger rule.");
              return;
            }
            setEditing("new");
          }}
          className={messagingPrimaryButton}
        >
          <Plus aria-hidden="true" className="size-3.5" />
          New rule
        </button>
      </div>

      {isLoading ? (
        <div className="flex min-h-40 items-center justify-center gap-2 text-xs text-charcoal/50">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Loading trigger rules…
        </div>
      ) : rules.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-charcoal/15 bg-charcoal/[0.025] px-5 py-10 text-center">
          <Zap aria-hidden="true" className="mx-auto size-5 text-charcoal/35" />
          <p className="mt-2 text-xs font-semibold text-charcoal">No automation rules configured</p>
          <p className="mt-1 text-[11px] text-charcoal/50">
            Connect a lead or site-visit event to a template to automate outbound messaging.
          </p>
        </div>
      ) : (
        <div className="mt-4 divide-y divide-charcoal/10 rounded-2xl border border-charcoal/10 bg-white">
          {rules.map((rule) => {
            const template = templates.find((item) => item.id === rule.template_id);
            return (
              <article key={rule.id} className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:p-5">
                <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${rule.enabled ? "bg-forest/10 text-forest" : "bg-charcoal/5 text-charcoal/40"}`}>
                  <Zap aria-hidden="true" className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-mono text-xs font-semibold text-charcoal">{rule.event}</h4>
                    <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${channelBadgeClasses(rule.channel)}`}>
                      {channelLabel(rule.channel)}
                    </span>
                    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${rule.enabled ? "bg-emerald-50 text-emerald-800" : "bg-charcoal/10 text-charcoal/50"}`}>
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[11px] leading-5 text-charcoal/55">
                    Sends <span className="font-semibold text-charcoal/75">{template?.name ?? "Deleted template"}</span>
                    {rule.delay_minutes > 0
                      ? ` after ${rule.delay_minutes.toLocaleString("en-IN")} minutes`
                      : " immediately"}
                  </p>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-center">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={rule.enabled}
                    aria-label={`${rule.enabled ? "Disable" : "Enable"} rule for ${rule.event}`}
                    disabled={pendingId === rule.id}
                    onClick={() => void toggleRule(rule)}
                    className={`relative h-6 w-11 rounded-full transition-colors disabled:opacity-50 ${rule.enabled ? "bg-forest" : "bg-charcoal/20"}`}
                  >
                    <span className={`absolute top-1 size-4 rounded-full bg-white shadow-sm transition-all ${rule.enabled ? "left-6" : "left-1"}`} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(rule)}
                    aria-label={`Edit rule for ${rule.event}`}
                    className="rounded-lg border border-charcoal/15 p-2 text-charcoal/60 hover:bg-charcoal/5"
                  >
                    <Pencil aria-hidden="true" className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void removeRule(rule)}
                    disabled={pendingId === rule.id}
                    aria-label={`Delete rule for ${rule.event}`}
                    className="rounded-lg border border-clay/20 p-2 text-clay hover:bg-clay-soft disabled:opacity-50"
                  >
                    <Trash2 aria-hidden="true" className="size-3.5" />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {editing ? (
        <TriggerRuleModal
          rule={editing === "new" ? null : editing}
          templates={templates}
          onClose={() => setEditing(null)}
          onSaved={async (message) => {
            setEditing(null);
            await invalidateRules();
            onNotice("success", message);
          }}
        />
      ) : null}
    </section>
  );
}

interface TriggerRuleModalProps {
  rule: TriggerRuleItem | null;
  templates: MessageTemplateItem[];
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}

function TriggerRuleModal({
  rule,
  templates,
  onClose,
  onSaved,
}: TriggerRuleModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState<MessageChannel>(rule?.channel ?? "WHATSAPP");
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RuleFormValues>({
    resolver: zodResolver(ruleSchema),
    defaultValues: {
      event: rule?.event ?? "lead.created",
      channel: rule?.channel ?? "WHATSAPP",
      templateId: rule?.template_id ?? "",
      delayMinutes: rule?.delay_minutes ?? 0,
      enabled: rule?.enabled ?? true,
    },
  });
  const compatibleTemplates = templates.filter((template) => template.channel === channel);

  const mutation = useMutation({
    mutationFn: async (values: RuleFormValues) => {
      if (rule) {
        return updateTriggerRule(rule.id, {
          template_id: values.templateId,
          delay_minutes: values.delayMinutes,
          enabled: values.enabled,
        });
      }
      return createTriggerRule({
        event: values.event.trim(),
        channel: values.channel as MessageChannel,
        template_id: values.templateId,
        delay_minutes: values.delayMinutes,
        enabled: values.enabled,
      });
    },
    onSuccess: async () => {
      await onSaved(rule ? "Trigger rule updated successfully." : "Trigger rule created successfully.");
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to save trigger rule."));
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={rule ? "Edit trigger rule" : "Create trigger rule"}
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-charcoal">
              {rule ? "Edit trigger rule" : "Create trigger rule"}
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              The template channel must match the rule channel.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close rule editor"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <form
          noValidate
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="p-5"
        >
          {error ? (
            <p role="alert" className="mb-4 rounded-xl border border-clay/25 bg-clay-soft px-3.5 py-2.5 text-xs text-clay">
              {error}
            </p>
          ) : null}

          <div className="space-y-4">
            <div>
              <label htmlFor="trigger-event" className={messagingLabelClasses}>Event name</label>
              <input
                id="trigger-event"
                list="known-messaging-events"
                disabled={Boolean(rule)}
                placeholder="lead.created"
                className={`${messagingInputClasses} font-mono`}
                {...register("event")}
              />
              <datalist id="known-messaging-events">
                {KNOWN_MESSAGING_EVENTS.map((event) => (
                  <option key={event} value={event} />
                ))}
              </datalist>
              {errors.event ? <p className="mt-1 text-[11px] text-clay">{errors.event.message}</p> : null}
            </div>

            <div>
              <label htmlFor="trigger-channel" className={messagingLabelClasses}>Channel</label>
              <select
                id="trigger-channel"
                disabled={Boolean(rule)}
                className={messagingInputClasses}
                {...register("channel", {
                  onChange: (event) => {
                    setChannel(event.target.value as MessageChannel);
                    setValue("templateId", "", { shouldValidate: true });
                  },
                })}
              >
                {CHANNELS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="trigger-template" className={messagingLabelClasses}>Message template</label>
              <select
                id="trigger-template"
                key={`${channel}-${rule?.id ?? "new"}`}
                className={messagingInputClasses}
                {...register("templateId")}
              >
                <option value="">Select a template</option>
                {compatibleTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.language}){template.is_active ? "" : " — disabled"}
                  </option>
                ))}
              </select>
              {compatibleTemplates.length === 0 ? (
                <p className="mt-1 text-[11px] text-clay">
                  No {channelLabel(channel)} templates exist. Create one in the Templates section first.
                </p>
              ) : null}
              {errors.templateId ? <p className="mt-1 text-[11px] text-clay">{errors.templateId.message}</p> : null}
            </div>

            <div>
              <label htmlFor="trigger-delay" className={messagingLabelClasses}>Delay (minutes)</label>
              <input
                id="trigger-delay"
                type="number"
                min="0"
                max="10080"
                step="1"
                className={messagingInputClasses}
                {...register("delayMinutes", { valueAsNumber: true })}
              />
              <p className="mt-1 text-[10px] text-charcoal/45">Use 0 to send immediately. Maximum 10,080 minutes (7 days).</p>
              {errors.delayMinutes ? <p className="mt-1 text-[11px] text-clay">{errors.delayMinutes.message}</p> : null}
            </div>

            <label className="flex cursor-pointer items-center gap-2.5 text-xs font-semibold text-charcoal">
              <input
                type="checkbox"
                className="size-4 rounded border-charcoal/25 accent-forest"
                {...register("enabled")}
              />
              Rule is enabled
            </label>
          </div>

          <div className="mt-5 flex justify-end gap-2.5 border-t border-charcoal/10 pt-4">
            <button type="button" onClick={onClose} className={messagingSecondaryButton}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className={messagingPrimaryButton}
            >
              {isSubmitting || mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : null}
              {rule ? "Save rule" : "Create rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
