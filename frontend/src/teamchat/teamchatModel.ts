export type TeamChannelKind = "CHANNEL" | "DIRECT";

export interface TeamStaffUser {
  id: string;
  full_name: string;
  email: string;
  role: "ADMIN" | "SALES_EXECUTIVE";
}

export interface TeamChannelMember {
  user_id: string;
  role: "OWNER" | "MODERATOR" | "MEMBER";
  joined_at: string;
  last_read_at: string | null;
  user: TeamStaffUser | null;
}

export interface TeamChannel {
  id: string;
  name: string;
  topic: string | null;
  kind: TeamChannelKind;
  is_general: boolean;
  created_by: string | null;
  created_at: string;
  unread_count: number;
  member_count: number;
  members: TeamChannelMember[];
}

export interface TeamMessage {
  id: string;
  channel_id: string;
  author_user_id: string | null;
  author: TeamStaffUser | null;
  body: string;
  mentions: string[];
  created_at: string;
  edited_at: string | null;
}

export interface TeamChannelListResponse {
  items: TeamChannel[];
  total: number;
  unread_total: number;
}

export interface TeamMessageListResponse {
  items: TeamMessage[];
  next_before: string | null;
}

export interface TeamUnreadResponse {
  total: number;
  by_channel: Record<string, number>;
}

export interface MessageDayGroup {
  day: string;
  messages: TeamMessage[];
}

/** Input may contain either newest-first pages or an already ascending stream. */
export function groupMessagesByDay(messages: readonly TeamMessage[]): MessageDayGroup[] {
  const ascending = [...messages].sort((left, right) =>
    left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id),
  );
  const groups = new Map<string, TeamMessage[]>();
  for (const message of ascending) {
    const day = message.created_at.slice(0, 10);
    groups.set(day, [...(groups.get(day) ?? []), message]);
  }
  return [...groups].map(([day, dayMessages]) => ({ day, messages: dayMessages }));
}

export function unreadBadgeLabel(count: number): string {
  if (!Number.isFinite(count) || count <= 0) return "0";
  return count > 99 ? "99+" : String(Math.floor(count));
}

export function filterMembersByName(
  members: readonly TeamStaffUser[], query: string,
): TeamStaffUser[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return [...members];
  return members.filter((member) =>
    `${member.full_name} ${member.email}`.toLocaleLowerCase().includes(needle),
  );
}

export function channelDisplayName(
  channel: TeamChannel, currentUserId: string, _staff: readonly TeamStaffUser[],
): string {
  if (channel.kind !== "DIRECT") return channel.name;
  // Direct channel names are opaque hashes (they no longer embed user ids),
  // so the peer is resolved from the channel's member list. The staff roster
  // is not consulted: without ids in the name it cannot identify the peer.
  const peer = channel.members.find((member) => member.user_id !== currentUserId)?.user;
  return peer?.full_name ?? "Direct message";
}
