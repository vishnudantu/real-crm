import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoaderCircle, X } from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { createMessageTemplate, updateMessageTemplate } from "../messagingApi";
import { errorMessage } from "../../shared/apiRequest";
import type {
  MessageChannel,
  MessageTemplateItem,
} from "../messagingModel";
import {
  CHANNELS,
  messagingInputClasses,
  messagingLabelClasses,
  messagingPrimaryButton,
  messagingSecondaryButton,
} from "./messagingUi";

const templateSchema = z.object({
  name: z.string().trim().min(1, "Enter a template name.").max(128),
  channel: z.enum(["WHATSAPP", "SMS", "EMAIL"]),
  language: z
    .string()
    .trim()
    .min(2, "Enter a language code.")
    .max(8)
    .regex(/^[a-z]{2,8}$/, "Use lowercase letters only, for example en or hi."),
  body: z.string().trim().min(1, "Enter the message body.").max(4000),
  providerTemplateName: z.string().trim().max(160),
  variablesText: z.string().max(600),
  isActive: z.boolean(),
});

type TemplateFormValues = z.infer<typeof templateSchema>;

interface MessageTemplateModalProps {
  template: MessageTemplateItem | null;
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}

export function MessageTemplateModal({
  template,
  onClose,
  onSaved,
}: MessageTemplateModalProps) {
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<TemplateFormValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: {
      name: template?.name ?? "",
      channel: template?.channel ?? "WHATSAPP",
      language: template?.language ?? "en",
      body: template?.body ?? "",
      providerTemplateName: template?.provider_template_name ?? "",
      variablesText: template?.variables.join(", ") ?? "",
      isActive: template?.is_active ?? true,
    },
  });
  const variables = watch("variablesText")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  const mutation = useMutation({
    mutationFn: async (values: TemplateFormValues) => {
      const parsedVariables = values.variablesText
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
        .slice(0, 25);
      const providerTemplateName = values.providerTemplateName.trim() || null;

      if (template) {
        return updateMessageTemplate(template.id, {
          name: values.name.trim(),
          body: values.body.trim(),
          provider_template_name: providerTemplateName,
          variables: parsedVariables,
          is_active: values.isActive,
        });
      }

      return createMessageTemplate({
        name: values.name.trim(),
        channel: values.channel as MessageChannel,
        language: values.language.trim(),
        body: values.body.trim(),
        provider_template_name: providerTemplateName,
        variables: parsedVariables,
      });
    },
    onSuccess: async (saved) => {
      await onSaved(
        template
          ? `${saved.name} updated successfully.`
          : `${saved.name} created successfully.`,
      );
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to save the template."));
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
        aria-label={template ? `Edit ${template.name}` : "Create message template"}
        className="max-h-[90svh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              {template ? "Edit message template" : "Create message template"}
            </h2>
            <p className="mt-1 text-[11px] text-charcoal/55">
              Use comma-separated variables to insert merge tags into the body.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close template editor"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
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

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label htmlFor="message-template-name" className={messagingLabelClasses}>
                Template name
              </label>
              <input
                id="message-template-name"
                placeholder="New lead welcome"
                className={messagingInputClasses}
                {...register("name")}
              />
              {errors.name ? <p className="mt-1 text-[11px] text-clay">{errors.name.message}</p> : null}
            </div>
            <div>
              <label htmlFor="message-template-channel" className={messagingLabelClasses}>
                Channel
              </label>
              <select
                id="message-template-channel"
                disabled={Boolean(template)}
                className={messagingInputClasses}
                {...register("channel")}
              >
                {CHANNELS.map((channel) => (
                  <option key={channel.value} value={channel.value}>{channel.label}</option>
                ))}
              </select>
              {template ? (
                <p className="mt-1 text-[10px] text-charcoal/45">Channel cannot change after creation.</p>
              ) : null}
            </div>
            <div>
              <label htmlFor="message-template-language" className={messagingLabelClasses}>
                Language code
              </label>
              <input
                id="message-template-language"
                placeholder="en"
                maxLength={8}
                disabled={Boolean(template)}
                className={messagingInputClasses}
                {...register("language")}
              />
              {errors.language ? <p className="mt-1 text-[11px] text-clay">{errors.language.message}</p> : null}
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="message-template-body" className={messagingLabelClasses}>
                Message body
              </label>
              <textarea
                id="message-template-body"
                rows={6}
                maxLength={4000}
                placeholder="Hi {lead_name}, thank you for your enquiry about {project_name}…"
                className={`${messagingInputClasses} resize-y leading-5`}
                {...register("body")}
              />
              {errors.body ? <p className="mt-1 text-[11px] text-clay">{errors.body.message}</p> : null}
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="message-template-variables" className={messagingLabelClasses}>
                Variables (comma separated)
              </label>
              <input
                id="message-template-variables"
                placeholder="lead_name, project_name, visit_date"
                className={messagingInputClasses}
                {...register("variablesText")}
              />
              <p className="mt-1 text-[10px] leading-4 text-charcoal/45">
                Reference them in the body as {"{lead_name}"}. Up to 25 variables.
              </p>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="message-template-provider-name" className={messagingLabelClasses}>
                Provider template name (optional)
              </label>
              <input
                id="message-template-provider-name"
                placeholder="Required for pre-approved WhatsApp templates"
                maxLength={160}
                className={messagingInputClasses}
                {...register("providerTemplateName")}
              />
            </div>
          </div>

          {variables.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {variables.map((variable, index) => (
                <span
                  key={`${variable}-${index}`}
                  className="rounded-md border border-charcoal/10 bg-charcoal/5 px-2 py-1 font-mono text-[10px] text-charcoal/65"
                >
                  {`{${variable}}`}
                </span>
              ))}
            </div>
          ) : null}

          <label className="mt-4 flex cursor-pointer items-center gap-2.5 text-xs font-semibold text-charcoal">
            <input
              type="checkbox"
              className="size-4 rounded border-charcoal/25 accent-forest"
              {...register("isActive")}
            />
            Template is active and available for trigger rules
          </label>

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
              {template ? "Save changes" : "Create template"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
