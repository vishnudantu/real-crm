import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, Send, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { sendTestMessage } from "../messagingApi";
import { errorMessage } from "../../shared/apiRequest";
import type { MessageChannel, MessageTemplateItem } from "../messagingModel";
import {
  CHANNELS,
  channelLabel,
  messagingInputClasses,
  messagingLabelClasses,
  messagingPrimaryButton,
  messagingSecondaryButton,
} from "./messagingUi";

const sendTestSchema = z
  .object({
    channel: z.enum(["WHATSAPP", "SMS", "EMAIL"]),
    toAddress: z
      .string()
      .trim()
      .min(3, "Enter a recipient address.")
      .max(320, "Recipient address is too long."),
    templateId: z.string(),
    body: z.string().trim().max(4000),
  })
  .refine((values) => Boolean(values.templateId || values.body), {
    path: ["body"],
    message: "Select a template or enter a message body.",
  });

type SendTestValues = z.infer<typeof sendTestSchema>;

interface SendTestModalProps {
  templates: MessageTemplateItem[];
  onClose: () => void;
  onSent: (message: string) => Promise<void>;
}

export function SendTestModal({
  templates,
  onClose,
  onSent,
}: SendTestModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState<MessageChannel>("WHATSAPP");
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const {
    register,
    handleSubmit,
    clearErrors,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<SendTestValues>({
    resolver: zodResolver(sendTestSchema),
    defaultValues: {
      channel: "WHATSAPP",
      toAddress: "",
      templateId: "",
      body: "",
    },
  });
  const compatibleTemplates = templates.filter((template) => template.channel === channel);

  const mutation = useMutation({
    mutationFn: async (values: SendTestValues) => {
      const selectedTemplate = templates.find(
        (template) => template.id === values.templateId,
      );
      return sendTestMessage({
        channel: selectedTemplate?.channel ?? values.channel,
        to_address: values.toAddress.trim(),
        ...(values.templateId ? { template_id: values.templateId } : {}),
        ...(values.body.trim() ? { body: values.body.trim() } : {}),
      });
    },
    onSuccess: async (delivery) => {
      await onSent(
        `Test ${channelLabel(delivery.channel)} message to ${delivery.to_address} queued (${delivery.status}).`,
      );
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to queue the test message."));
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
        aria-label="Send a test message"
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-charcoal">Send a test message</h2>
            <p className="mt-1 text-[11px] leading-4 text-charcoal/55">
              Queue a real delivery through the configured channel provider. Use a
              phone number with country code for WhatsApp and SMS.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close test message form"
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
              <label htmlFor="test-message-channel" className={messagingLabelClasses}>Channel</label>
              <select
                id="test-message-channel"
                className={messagingInputClasses}
                {...register("channel", {
                  onChange: (event) => {
                    setChannel(event.target.value as MessageChannel);
                    setValue("templateId", "", { shouldValidate: true });
                    clearErrors("body");
                  },
                })}
              >
                {CHANNELS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="test-message-recipient" className={messagingLabelClasses}>
                Recipient
              </label>
              <input
                id="test-message-recipient"
                placeholder={channel === "EMAIL" ? "buyer@example.com" : "+919876543210"}
                autoComplete="off"
                className={messagingInputClasses}
                {...register("toAddress")}
              />
              {errors.toAddress ? <p className="mt-1 text-[11px] text-clay">{errors.toAddress.message}</p> : null}
            </div>

            <div>
              <label htmlFor="test-message-template" className={messagingLabelClasses}>
                Template (optional)
              </label>
              <select
                id="test-message-template"
                key={channel}
                className={messagingInputClasses}
                {...register("templateId", {
                  onChange: () => clearErrors("body"),
                })}
              >
                <option value="">Custom message body</option>
                {compatibleTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.language})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] leading-4 text-charcoal/45">
                When a template is selected, its channel is used and the custom
                body below overrides its content only if provided.
              </p>
            </div>

            <div>
              <label htmlFor="test-message-body" className={messagingLabelClasses}>
                Custom body (optional with template)
              </label>
              <textarea
                id="test-message-body"
                rows={5}
                maxLength={4000}
                placeholder="Hello from PropFlow. This is a test message."
                className={`${messagingInputClasses} resize-y leading-5`}
                {...register("body", {
                  onChange: () => {
                    if (errors.body) clearErrors("body");
                  },
                })}
              />
              {errors.body?.message ? <p className="mt-1 text-[11px] text-clay">{errors.body.message}</p> : null}
            </div>
          </div>

          <div className="mt-5 flex justify-end gap-2.5 border-t border-charcoal/10 pt-4">
            <button type="button" onClick={onClose} className={messagingSecondaryButton}>Cancel</button>
            <button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className={messagingPrimaryButton}
            >
              {isSubmitting || mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
              ) : (
                <Send aria-hidden="true" className="size-3.5" />
              )}
              Queue test message
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
