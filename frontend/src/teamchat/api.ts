import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  TeamChannel,
  TeamChannelListResponse,
  TeamMessage,
  TeamMessageListResponse,
  TeamStaffUser,
  TeamUnreadResponse,
} from "./teamchatModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export function fetchTeamChannels(): Promise<TeamChannelListResponse> {
  return bearerRequest<TeamChannelListResponse>("/teamchat/channels", SESSION);
}

export function fetchTeamUnread(): Promise<TeamUnreadResponse> {
  return bearerRequest<TeamUnreadResponse>("/teamchat/unread", SESSION);
}

export function fetchTeamMembers(search = ""): Promise<TeamStaffUser[]> {
  const suffix = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return bearerRequest<TeamStaffUser[]>(`/teamchat/members${suffix}`, SESSION);
}

export function fetchTeamMessages(
  channelId: string, before?: string, limit = 50,
): Promise<TeamMessageListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set("before", before);
  return bearerRequest<TeamMessageListResponse>(
    `/teamchat/channels/${encodeURIComponent(channelId)}/messages?${params}`, SESSION,
  );
}

export function createTeamChannel(payload: {
  name: string;
  topic?: string | null;
  member_ids: string[];
}): Promise<TeamChannel> {
  return bearerRequest<TeamChannel>("/teamchat/channels", SESSION, {
    method: "POST", body: JSON.stringify(payload),
  });
}

export function ensureGeneralChannel(): Promise<TeamChannel> {
  return bearerRequest<TeamChannel>("/teamchat/channels/general", SESSION, { method: "POST" });
}

export function createDirectChannel(userId: string): Promise<TeamChannel> {
  return bearerRequest<TeamChannel>("/teamchat/direct", SESSION, {
    method: "POST", body: JSON.stringify({ user_id: userId }),
  });
}

export function sendTeamMessage(
  channelId: string, payload: { body: string; mentions: string[] },
): Promise<TeamMessage> {
  return bearerRequest<TeamMessage>(
    `/teamchat/channels/${encodeURIComponent(channelId)}/messages`, SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function markTeamChannelRead(channelId: string): Promise<unknown> {
  return bearerRequest<unknown>(
    `/teamchat/channels/${encodeURIComponent(channelId)}/read`, SESSION, { method: "POST" },
  );
}
