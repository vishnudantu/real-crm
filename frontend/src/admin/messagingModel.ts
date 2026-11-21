export type MessageChannel = "WHATSAPP" | "SMS" | "EMAIL";

export type DeliveryStatus =
  | "QUEUED"
  | "SENDING"
  | "SENT"
  | "FAILED"
  | "CANCELLED";

export interface MessageTemplateItem {
  id: string;
  name: string;
  channel: MessageChannel;
  language: string;
  body: string;
  provider_template_name: string | null;
  variables: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MessageTemplateListResponse {
  items: MessageTemplateItem[];
  total: number;
}

export interface CreateMessageTemplatePayload {
  name: string;
  channel: MessageChannel;
  language: string;
  body: string;
  provider_template_name: string | null;
  variables: string[];
}

export interface UpdateMessageTemplatePayload {
  name?: string;
  body?: string;
  provider_template_name?: string | null;
  variables?: string[];
  is_active?: boolean;
}

export interface TriggerRuleItem {
  id: string;
  event: string;
  channel: MessageChannel;
  template_id: string;
  enabled: boolean;
  delay_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface TriggerRuleListResponse {
  items: TriggerRuleItem[];
  total: number;
}

export interface CreateTriggerRulePayload {
  event: string;
  channel: MessageChannel;
  template_id: string;
  enabled: boolean;
  delay_minutes: number;
}

export interface UpdateTriggerRulePayload {
  enabled?: boolean;
  delay_minutes?: number;
  template_id?: string;
}

export interface MessageDeliveryItem {
  id: string;
  channel: MessageChannel;
  to_address: string;
  body: string;
  provider: string;
  status: DeliveryStatus;
  provider_msg_id: string | null;
  error: string | null;
  attempts: number;
  event: string;
  entity_type: string | null;
  entity_id: string | null;
  next_attempt_at: string;
  sent_at: string | null;
  created_at: string;
}

export interface MessageDeliveryListResponse {
  items: MessageDeliveryItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface FetchDeliveriesParams {
  page?: number;
  pageSize?: number;
  status?: DeliveryStatus | "ALL";
  channel?: MessageChannel | "ALL";
}

export interface SendTestPayload {
  channel: MessageChannel;
  to_address: string;
  template_id?: string;
  body?: string;
}
