import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  CallRecord,
  CallRecording,
  CallTokenResponse,
  ChannelConversation,
  ChannelConversationDetail,
  ChannelCredentialSummary,
  ChannelMessage,
  ChannelType,
  EmbedSnippet,
  InboxResponse,
} from "./omnichannelModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export interface InboxQuery {
  channel?: ChannelType;
  assignedToId?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export function fetchInbox(query: InboxQuery = {}): Promise<InboxResponse> {
  const params = new URLSearchParams();
  if (query.channel) params.set("channel", query.channel);
  if (query.assignedToId) params.set("assigned_to_id", query.assignedToId);
  if (query.status) params.set("status", query.status);
  if (query.limit) params.set("limit", String(query.limit));
  if (query.offset) params.set("offset", String(query.offset));
  const suffix = params.size ? `?${params}` : "";
  return bearerRequest<InboxResponse>(`/omnichannel/inbox${suffix}`, SESSION);
}

export function fetchConversation(id: string): Promise<ChannelConversationDetail> {
  return bearerRequest<ChannelConversationDetail>(
    `/omnichannel/conversations/${encodeURIComponent(id)}`,
    SESSION,
  );
}

export function sendChannelReply(conversationId: string, text: string): Promise<ChannelMessage> {
  return bearerRequest<ChannelMessage>("/omnichannel/messages", SESSION, {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, text }),
  });
}

export function assignConversation(
  conversationId: string,
  assignedToId: string | null,
): Promise<ChannelConversation> {
  return bearerRequest<ChannelConversation>(
    `/omnichannel/conversations/${encodeURIComponent(conversationId)}/assign`,
    SESSION,
    { method: "POST", body: JSON.stringify({ assigned_to_id: assignedToId }) },
  );
}

export function fetchChannelCredentials(): Promise<ChannelCredentialSummary[]> {
  return bearerRequest<ChannelCredentialSummary[]>("/omnichannel/credentials", SESSION);
}

export interface ChannelConfigPayload {
  channel: ChannelType;
  provider: string;
  credentials: Record<string, string>;
  config: Record<string, unknown>;
  is_active: boolean;
  webhook_verify_token?: string;
}

export function configureChannel(
  channel: ChannelType,
  payload: ChannelConfigPayload,
): Promise<ChannelCredentialSummary> {
  return bearerRequest<ChannelCredentialSummary>(
    `/omnichannel/credentials/${encodeURIComponent(channel)}`,
    SESSION,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export interface StartCallPayload {
  lead_id?: string;
  conversation_id?: string;
  destination?: string;
  record?: boolean;
  recording_consent_confirmed?: boolean;
}

export function startCall(payload: StartCallPayload): Promise<CallTokenResponse> {
  return bearerRequest<CallTokenResponse>("/omnichannel/calls", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function joinCall(callId: string, displayName?: string): Promise<CallTokenResponse> {
  return bearerRequest<CallTokenResponse>(
    `/omnichannel/calls/${encodeURIComponent(callId)}/join`,
    SESSION,
    { method: "POST", body: JSON.stringify({ display_name: displayName }) },
  );
}

export function endCall(callId: string): Promise<CallRecord> {
  return bearerRequest<CallRecord>(
    `/omnichannel/calls/${encodeURIComponent(callId)}/end`,
    SESSION,
    { method: "POST" },
  );
}

export function startRecording(callId: string): Promise<CallRecording> {
  return bearerRequest<CallRecording>(
    `/omnichannel/calls/${encodeURIComponent(callId)}/recordings?consent_confirmed=true`,
    SESSION,
    { method: "POST" },
  );
}

export function listRecordings(callId: string): Promise<CallRecording[]> {
  return bearerRequest<CallRecording[]>(
    `/omnichannel/calls/${encodeURIComponent(callId)}/recordings`,
    SESSION,
  );
}

export function fetchEmbedSnippet(): Promise<EmbedSnippet> {
  return bearerRequest<EmbedSnippet>("/tenancy/me/embed-snippet", SESSION);
}
