export type ChannelType =
  | "WEB_CHAT"
  | "WHATSAPP"
  | "INSTAGRAM"
  | "MESSENGER"
  | "SMS"
  | "EMAIL"
  | "VOICE";

export type MessageDirection = "INBOUND" | "OUTBOUND";

export interface ChannelConversation {
  id: string;
  lead_id: string | null;
  contact_id: string | null;
  assigned_to_id: string | null;
  channel: ChannelType;
  external_thread_id: string;
  contact_name: string | null;
  contact_handle: string | null;
  contact_avatar_url: string | null;
  status: string;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChannelMessage {
  id: string;
  conversation_id: string;
  channel: ChannelType;
  direction: MessageDirection;
  sender_id: string | null;
  sender_handle: string | null;
  external_message_id: string | null;
  content_type: string;
  content: string | null;
  media_url: string | null;
  status: string;
  error: string | null;
  created_at: string;
}

export interface ChannelConversationDetail extends ChannelConversation {
  messages: ChannelMessage[];
}

export interface InboxResponse {
  items: ChannelConversation[];
  total: number;
  unread_total: number;
}

export interface ChannelCredentialSummary {
  id: string;
  channel: ChannelType;
  provider: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CallRecord {
  id: string;
  lead_id: string | null;
  conversation_id: string | null;
  agent_id: string;
  direction: "INBOUND" | "OUTBOUND";
  status: string;
  provider: string;
  room_name: string;
  destination: string | null;
  duration_seconds: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface CallTokenResponse {
  call: CallRecord;
  participant_token: string;
  connection: { mode: string; url: string | null };
}

export interface CallRecording {
  id: string;
  call_id: string;
  egress_id: string | null;
  status: string;
  storage_url: string | null;
  mime_type: string;
  duration_seconds: number;
  size_bytes: number;
  created_at: string;
  completed_at: string | null;
}

export interface EmbedSnippet {
  enabled: boolean;
  slug?: string;
  embed_url: string | null;
  snippet: string | null;
  installation?: string;
}

export interface FeatureCatalogItem {
  feature: string;
  label: string;
  description: string;
  enabled: boolean;
  source: "TENANT_OVERRIDE" | "PLAN" | "CATALOG_DEFAULT";
  reason: string | null;
  updated_at: string | null;
}
