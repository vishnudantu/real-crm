import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  CreateMessageTemplatePayload,
  CreateTriggerRulePayload,
  FetchDeliveriesParams,
  MessageDeliveryItem,
  MessageDeliveryListResponse,
  MessageTemplateItem,
  MessageTemplateListResponse,
  SendTestPayload,
  TriggerRuleItem,
  TriggerRuleListResponse,
  UpdateMessageTemplatePayload,
  UpdateTriggerRulePayload,
} from "./messagingModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export function fetchMessageTemplates(): Promise<MessageTemplateListResponse> {
  return bearerRequest<MessageTemplateListResponse>("/messaging/templates", SESSION);
}

export function createMessageTemplate(
  payload: CreateMessageTemplatePayload,
): Promise<MessageTemplateItem> {
  return bearerRequest<MessageTemplateItem>("/messaging/templates", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMessageTemplate(
  templateId: string,
  payload: UpdateMessageTemplatePayload,
): Promise<MessageTemplateItem> {
  return bearerRequest<MessageTemplateItem>(
    `/messaging/templates/${templateId}`,
    SESSION,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function deleteMessageTemplate(templateId: string): Promise<void> {
  return bearerRequest<void>(`/messaging/templates/${templateId}`, SESSION, {
    method: "DELETE",
  });
}

export function fetchTriggerRules(): Promise<TriggerRuleListResponse> {
  return bearerRequest<TriggerRuleListResponse>("/messaging/rules", SESSION);
}

export function createTriggerRule(
  payload: CreateTriggerRulePayload,
): Promise<TriggerRuleItem> {
  return bearerRequest<TriggerRuleItem>("/messaging/rules", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTriggerRule(
  ruleId: string,
  payload: UpdateTriggerRulePayload,
): Promise<TriggerRuleItem> {
  return bearerRequest<TriggerRuleItem>(
    `/messaging/rules/${ruleId}`,
    SESSION,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function deleteTriggerRule(ruleId: string): Promise<void> {
  return bearerRequest<void>(`/messaging/rules/${ruleId}`, SESSION, {
    method: "DELETE",
  });
}

export function fetchMessageDeliveries(
  params: FetchDeliveriesParams = {},
): Promise<MessageDeliveryListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));
  if (params.status && params.status !== "ALL") {
    query.set("status", params.status);
  }
  if (params.channel && params.channel !== "ALL") {
    query.set("channel", params.channel);
  }

  const queryString = query.toString();
  return bearerRequest<MessageDeliveryListResponse>(
    queryString ? `/messaging/deliveries?${queryString}` : "/messaging/deliveries",
    SESSION,
  );
}

export function sendTestMessage(
  payload: SendTestPayload,
): Promise<MessageDeliveryItem> {
  return bearerRequest<MessageDeliveryItem>("/messaging/send-test", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
