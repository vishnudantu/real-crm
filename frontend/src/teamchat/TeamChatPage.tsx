import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Hash,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Send,
  UsersRound,
  X,
} from "lucide-react";
import { useOptionalAdminUser } from "../admin/AdminAuthGuard";
import { useOptionalSalesUser } from "../sales/SalesAuthGuard";
import { errorMessage } from "../shared/apiRequest";
import {
  createDirectChannel,
  createTeamChannel,
  ensureGeneralChannel,
  fetchTeamChannels,
  fetchTeamMembers,
  fetchTeamMessages,
  fetchTeamUnread,
  markTeamChannelRead,
  sendTeamMessage,
} from "./api";
import { channelDisplayName, groupMessagesByDay, unreadBadgeLabel } from "./teamchatModel";
import type { TeamChannel, TeamMessage } from "./teamchatModel";
import { StaffPicker } from "./StaffPicker";
import { NewChannelDialog } from "./NewChannelDialog";

const REFRESH_INTERVAL_MS = 20_000;
const COMPOSER_MAX_LENGTH = 4000;

interface ChatUser {
  id: string;
  full_name: string;
  role: { name: string };
}

interface SendVariables {
  channelId: string;
  body: string;
  mentions: string[];
}

interface OptimisticContext {
  previous?: TeamMessage[];
  temporaryId: string;
}

function dayLabel(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(date);
}

function timeLabel(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

function authorInitials(message: TeamMessage): string {
  return (message.author?.full_name ?? "Former staff").split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
}

export function TeamChatPage() {
  const location = useLocation();
  const admin = useOptionalAdminUser();
  const sales = useOptionalSalesUser();
  const isSalesRoute = location.pathname.startsWith("/sales");
  const activeUser = isSalesRoute ? sales?.user : admin?.user;
  // Rendered under either guard; one of the two contexts is present on a matched
  // route. Use a stable fallback so all hooks below run unconditionally (Rules
  // of Hooks); the missing-session case is handled at render time.
  const currentUser: ChatUser = activeUser ?? { id: "", full_name: "", role: { name: "" } };
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileThreadOpen, setMobileThreadOpen] = useState(false);
  const [newChannelOpen, setNewChannelOpen] = useState(false);
  const [newDirectOpen, setNewDirectOpen] = useState(false);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [composer, setComposer] = useState("");
  const [mentions, setMentions] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [extraMessages, setExtraMessages] = useState<TeamMessage[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const channelsQuery = useQuery({
    queryKey: ["teamchat", "channels"],
    queryFn: fetchTeamChannels,
    refetchInterval: REFRESH_INTERVAL_MS,
  });
  const unreadQuery = useQuery({
    queryKey: ["teamchat", "unread"],
    queryFn: fetchTeamUnread,
    refetchInterval: REFRESH_INTERVAL_MS,
  });
  const membersQuery = useQuery({
    queryKey: ["teamchat", "members"],
    queryFn: () => fetchTeamMembers(),
    staleTime: 60_000,
  });
  const channels = useMemo(() => channelsQuery.data?.items ?? [], [channelsQuery.data]);
  const staff = useMemo(() => membersQuery.data ?? [], [membersQuery.data]);
  const selectedChannel = channels.find((channel) => channel.id === selectedId) ?? null;
  const effectiveSelectedId = selectedChannel?.id ?? null;
  const messagesQuery = useQuery({
    queryKey: ["teamchat", "messages", effectiveSelectedId],
    queryFn: () => fetchTeamMessages(effectiveSelectedId ?? ""),
    enabled: effectiveSelectedId !== null,
    refetchInterval: REFRESH_INTERVAL_MS,
  });
  const messages = useMemo(
    () => [...extraMessages, ...(messagesQuery.data?.items ?? [])],
    [extraMessages, messagesQuery.data],
  );
  const dayGroups = useMemo(() => groupMessagesByDay(messages), [messages]);

  const invalidateChat = () => {
    void queryClient.invalidateQueries({ queryKey: ["teamchat", "channels"] });
    void queryClient.invalidateQueries({ queryKey: ["teamchat", "unread"] });
  };
  const selectChannel = (channel: TeamChannel) => {
    setSelectedId(channel.id);
    setMobileThreadOpen(true);
    setExtraMessages([]);
    setComposer("");
    setMentions([]);
    setMentionOpen(false);
    setFormError(null);
    void markTeamChannelRead(channel.id).then(invalidateChat).catch(() => undefined);
  };

  const createChannelMutation = useMutation({
    mutationFn: createTeamChannel,
    onSuccess: (channel) => {
      setNewChannelOpen(false);
      invalidateChat();
      selectChannel(channel);
    },
    onError: (error: unknown) => setFormError(errorMessage(error, "Could not create this channel.")),
  });
  const directMutation = useMutation({
    mutationFn: createDirectChannel,
    onSuccess: (channel) => {
      setNewDirectOpen(false);
      invalidateChat();
      selectChannel(channel);
    },
    onError: (error: unknown) => setFormError(errorMessage(error, "Could not start this direct chat.")),
  });
  const generalMutation = useMutation({
    mutationFn: ensureGeneralChannel,
    onSuccess: (channel) => {
      invalidateChat();
      selectChannel(channel);
    },
    onError: (error: unknown) => setFormError(errorMessage(error, "Could not open the general channel.")),
  });
  const sendMutation = useMutation<TeamMessage, unknown, SendVariables, OptimisticContext>({
    mutationFn: ({ channelId, body, mentions: mentionIds }) => sendTeamMessage(channelId, { body, mentions: mentionIds }),
    onMutate: async ({ channelId, body, mentions: mentionIds }) => {
      await queryClient.cancelQueries({ queryKey: ["teamchat", "messages", channelId] });
      const previous = queryClient.getQueryData<TeamMessage[]>(["teamchat", "messages", channelId]);
      const temporaryId = `optimistic-${crypto.randomUUID()}`;
      const optimistic: TeamMessage = {
        id: temporaryId,
        channel_id: channelId,
        author_user_id: currentUser.id,
        author: { id: currentUser.id, full_name: currentUser.full_name, email: "", role: currentUser.role.name === "ADMIN" ? "ADMIN" : "SALES_EXECUTIVE" },
        body,
        mentions: mentionIds,
        created_at: new Date().toISOString(),
        edited_at: null,
      };
      queryClient.setQueryData(["teamchat", "messages", channelId], (current: TeamMessage[] | undefined) => [optimistic, ...(current ?? [])]);
      return { previous, temporaryId };
    },
    onError: (_error, { channelId }, context) => {
      queryClient.setQueryData(["teamchat", "messages", channelId], context?.previous ?? []);
      setFormError("Message could not be sent. Your text is still in the composer.");
    },
    onSuccess: (message, { channelId }, context) => {
      queryClient.setQueryData(["teamchat", "messages", channelId], (current: TeamMessage[] | undefined) =>
        (current ?? []).map((item) => item.id === context?.temporaryId ? message : item),
      );
      invalidateChat();
    },
  });
  const loadOlderMutation = useMutation({
    mutationFn: ({ channelId, before }: { channelId: string; before: string }) => fetchTeamMessages(channelId, before),
    onSuccess: (page) => setExtraMessages((current) => [...current, ...page.items]),
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [effectiveSelectedId, dayGroups.length, messages.length]);

  const submitMessage = (event?: FormEvent) => {
    event?.preventDefault();
    const body = composer.trim();
    if (!effectiveSelectedId || !body || sendMutation.isPending) return;
    if (body.length > COMPOSER_MAX_LENGTH) {
      setFormError("Messages must be 4,000 characters or fewer.");
      return;
    }
    setFormError(null);
    sendMutation.mutate({ channelId: effectiveSelectedId, body, mentions });
    setComposer("");
    setMentions([]);
    setMentionOpen(false);
  };

  const displayName = (channel: TeamChannel) => channelDisplayName(channel, currentUser.id, staff);
  const otherChannels = channels.filter((channel) => channel.kind === "CHANNEL");
  const directChannels = channels.filter((channel) => channel.kind === "DIRECT");
  const totalUnread = unreadQuery.data?.total ?? channelsQuery.data?.unread_total ?? 0;

  // All hooks above run unconditionally; gate the actual chat UI on a real session.
  if (!activeUser) {
    return (
      <div className="flex h-[34rem] items-center justify-center p-8 text-sm text-charcoal/60">
        Team chat requires an authenticated staff session.
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100svh-12rem)] min-h-[34rem] flex-col gap-4 lg:h-[calc(100svh-10rem)]">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-charcoal">
            <UsersRound aria-hidden="true" className="size-5" /> Team chat
            {totalUnread > 0 && <span className="rounded-full bg-forest px-2 py-0.5 text-xs font-bold text-ivory">{unreadBadgeLabel(totalUnread)} unread</span>}
          </h1>
          <p className="mt-0.5 text-sm text-charcoal/60">Private channels and direct messages for your staff.</p>
        </div>
        <div className="flex items-center gap-2">
          {currentUser.role.name === "ADMIN" && (
            <button type="button" onClick={() => generalMutation.mutate()} disabled={generalMutation.isPending} className="rounded-xl border border-charcoal/15 px-3 py-2 text-xs font-semibold text-charcoal/70 hover:bg-charcoal/5 disabled:opacity-50">General</button>
          )}
          <button type="button" onClick={() => { setNewDirectOpen((value) => !value); setFormError(null); }} className="rounded-xl border border-charcoal/15 px-3 py-2 text-xs font-semibold text-charcoal/70 hover:bg-charcoal/5">Direct message</button>
          <button type="button" onClick={() => { setNewChannelOpen(true); setFormError(null); }} className="inline-flex items-center gap-1.5 rounded-xl bg-charcoal px-3 py-2 text-xs font-semibold text-ivory">
            <Plus aria-hidden="true" className="size-4" /> New channel
          </button>
        </div>
      </header>

      {formError && <div role="alert" className="shrink-0 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">{formError}</div>}
      {newDirectOpen && (
        <section className="shrink-0 rounded-2xl border border-charcoal/10 bg-white p-3 shadow-xs">
          <div className="mb-2 flex items-center justify-between"><h2 className="text-sm font-semibold">Start a direct chat</h2><button type="button" onClick={() => setNewDirectOpen(false)} aria-label="Close direct message picker"><X className="size-4" /></button></div>
          <StaffPicker members={staff.filter((person) => person.id !== currentUser.id)} loading={membersQuery.isPending} selectedIds={directMutation.isPending ? ["pending"] : []} onToggle={(id) => directMutation.mutate(id)} />
        </section>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        <aside className={`${mobileThreadOpen ? "hidden md:flex" : "flex"} w-full flex-col rounded-2xl border border-charcoal/10 bg-white shadow-xs md:w-72 md:shrink-0`}>
          <div className="border-b border-charcoal/10 px-4 py-3"><p className="text-xs font-semibold tracking-wider text-charcoal/55 uppercase">Your conversations</p></div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {channelsQuery.isPending && <div className="flex justify-center py-12 text-charcoal/55"><LoaderCircle aria-label="Loading channels" className="size-5 animate-spin" /></div>}
            {channelsQuery.isError && <div role="alert" className="p-3 text-sm text-rose-700">Channels could not be loaded. <button type="button" className="font-semibold underline" onClick={() => void channelsQuery.refetch()}>Try again</button></div>}
            {!channelsQuery.isPending && channels.length === 0 && <div className="px-4 py-12 text-center text-sm text-charcoal/55"><MessageSquareText className="mx-auto mb-2 size-8 text-charcoal/25" /><p>No conversations yet.</p><p className="mt-1 text-xs">Create a channel or start a direct message.</p></div>}
            <ChannelSection label="Channels" channels={otherChannels} selectedId={effectiveSelectedId} displayName={displayName} onSelect={selectChannel} />
            <ChannelSection label="Direct messages" channels={directChannels} selectedId={effectiveSelectedId} displayName={displayName} onSelect={selectChannel} direct />
          </div>
        </aside>

        <section className={`${mobileThreadOpen ? "flex" : "hidden md:flex"} min-w-0 flex-1 flex-col rounded-2xl border border-charcoal/10 bg-white shadow-xs`}>
          {!selectedChannel ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center text-charcoal/55">
              <MessageSquareText aria-hidden="true" className="size-12 text-charcoal/20" />
              <p className="text-sm">Select a conversation to start chatting.</p>
            </div>
          ) : (
            <>
              <div className="flex shrink-0 items-center gap-3 border-b border-charcoal/10 px-4 py-3">
                <button type="button" onClick={() => setMobileThreadOpen(false)} className="rounded-lg border border-charcoal/10 px-2 py-1 text-xs md:hidden">Back</button>
                <span className="grid size-9 place-items-center rounded-xl bg-forest/10 text-forest">{selectedChannel.kind === "DIRECT" ? <AtSign className="size-4" /> : <Hash className="size-4" />}</span>
                <div className="min-w-0"><h2 className="truncate text-sm font-semibold">{displayName(selectedChannel)}</h2><p className="truncate text-xs text-charcoal/55">{selectedChannel.topic ?? `${selectedChannel.member_count} staff members`}</p></div>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto bg-[#FAFAF7] px-4 py-4">
                {messagesQuery.data?.next_before && <div className="mb-4 text-center"><button type="button" onClick={() => messagesQuery.data && loadOlderMutation.mutate({ channelId: selectedChannel.id, before: messagesQuery.data.next_before ?? "" })} disabled={loadOlderMutation.isPending} className="rounded-full border border-charcoal/15 bg-white px-3 py-1.5 text-xs font-semibold text-charcoal/65 disabled:opacity-50">{loadOlderMutation.isPending ? "Loading…" : "Load older messages"}</button></div>}
                {messagesQuery.isPending ? <div className="flex h-full items-center justify-center"><LoaderCircle aria-label="Loading messages" className="size-6 animate-spin text-charcoal/45" /></div> : messagesQuery.isError ? <div role="alert" className="py-8 text-center text-sm text-rose-700">Messages could not be loaded. <button type="button" className="font-semibold underline" onClick={() => void messagesQuery.refetch()}>Try again</button></div> : dayGroups.length === 0 ? <p className="py-16 text-center text-sm text-charcoal/50">No messages yet. Say hello to your team.</p> : dayGroups.map((group) => (
                  <div key={group.day}>
                    <div className="my-4 flex items-center gap-3" role="separator" aria-label={dayLabel(group.day)}><span className="h-px flex-1 bg-charcoal/10" /><span className="text-[0.65rem] font-semibold tracking-wide text-charcoal/50 uppercase">{dayLabel(group.day)}</span><span className="h-px flex-1 bg-charcoal/10" /></div>
                    <div className="space-y-3">{group.messages.map((message) => <MessageBubble key={message.id} message={message} own={message.author_user_id === currentUser.id} staffNames={new Map(staff.map((person) => [person.id, person.full_name]))} />)}</div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form onSubmit={submitMessage} className="relative shrink-0 border-t border-charcoal/10 p-3">
                {mentionOpen && <div className="absolute right-3 bottom-full left-3 z-10 mb-2 shadow-xl"><StaffPicker members={staff.filter((person) => person.id !== currentUser.id)} loading={membersQuery.isPending} selectedIds={mentions} onToggle={(id) => setMentions((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])} /></div>}
                {mentions.length > 0 && <p className="mb-1.5 truncate text-xs text-forest">Mentioning: {staff.filter((person) => mentions.includes(person.id)).map((person) => person.full_name).join(", ")}</p>}
                <div className="flex items-end gap-2">
                  <button type="button" onClick={() => setMentionOpen((value) => !value)} aria-label="Mention a staff member" aria-expanded={mentionOpen} className="grid size-10 shrink-0 place-items-center rounded-xl border border-charcoal/15 text-charcoal/60 hover:bg-charcoal/5"><AtSign className="size-4" /></button>
                  <textarea aria-label="Message" rows={2} maxLength={COMPOSER_MAX_LENGTH} value={composer} onChange={(event) => setComposer(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitMessage(); } }} placeholder="Write a message…" className="min-w-0 flex-1 resize-none rounded-xl border border-charcoal/15 px-3 py-2.5 text-sm outline-none focus:border-forest" />
                  <button type="submit" aria-label="Send message" disabled={!composer.trim() || sendMutation.isPending} className="grid size-10 shrink-0 place-items-center rounded-xl bg-charcoal text-ivory disabled:opacity-40">{sendMutation.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}</button>
                </div>
                <p className="mt-1.5 text-[0.68rem] text-charcoal/45">Enter to send · Shift+Enter for a new line · {composer.length}/4,000</p>
              </form>
            </>
          )}
        </section>
      </div>

      {newChannelOpen && <NewChannelDialog members={staff.filter((person) => person.id !== currentUser.id)} membersLoading={membersQuery.isPending} pending={createChannelMutation.isPending} error={formError} onClose={() => setNewChannelOpen(false)} onCreate={(payload) => { setFormError(null); createChannelMutation.mutate(payload); }} />}
    </div>
  );
}

interface ChannelSectionProps {
  label: string;
  channels: TeamChannel[];
  selectedId: string | null;
  displayName: (channel: TeamChannel) => string;
  onSelect: (channel: TeamChannel) => void;
  direct?: boolean;
}

function ChannelSection({ label, channels, selectedId, displayName, onSelect, direct = false }: ChannelSectionProps) {
  if (channels.length === 0) return null;
  return <div className="mb-3"><p className="px-2 py-1.5 text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">{label}</p><ul>{channels.map((channel) => <li key={channel.id}><button type="button" onClick={() => onSelect(channel)} className={`flex w-full items-center gap-2 rounded-xl px-2.5 py-2.5 text-left transition-colors ${selectedId === channel.id ? "bg-forest/10 text-forest" : "text-charcoal hover:bg-charcoal/5"}`}><span className="grid size-7 shrink-0 place-items-center rounded-lg bg-charcoal/5">{direct ? <AtSign className="size-3.5" /> : <Hash className="size-3.5" />}</span><span className="min-w-0 flex-1 truncate text-sm font-semibold">{displayName(channel)}</span>{channel.unread_count > 0 && <span aria-label={`${channel.unread_count} unread messages`} className="rounded-full bg-forest px-1.5 py-0.5 text-[0.65rem] font-bold text-ivory">{unreadBadgeLabel(channel.unread_count)}</span>}</button></li>)}</ul></div>;
}

interface MessageBubbleProps {
  message: TeamMessage;
  own: boolean;
  staffNames: ReadonlyMap<string, string>;
}

function MessageBubble({ message, own, staffNames }: MessageBubbleProps) {
  return <div className={`flex gap-2 ${own ? "justify-end" : "justify-start"}`}>{!own && <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-charcoal/10 text-[0.65rem] font-bold text-charcoal">{authorInitials(message)}</span>}<div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm shadow-xs ${own ? "rounded-br-sm bg-forest text-ivory" : "rounded-bl-sm border border-charcoal/10 bg-white text-charcoal"}`}>{!own && <p className="mb-1 text-xs font-semibold text-forest">{message.author?.full_name ?? "Former staff member"}</p>}<p className="whitespace-pre-wrap break-words">{message.body}</p>{message.mentions.length > 0 && <p className={`mt-1 text-[0.65rem] ${own ? "text-ivory/70" : "text-charcoal/50"}`}>Mentions: {message.mentions.map((id) => staffNames.get(id) ?? "Staff member").join(", ")}</p>}<p className={`mt-1 text-right text-[0.65rem] ${own ? "text-ivory/65" : "text-charcoal/45"}`}>{timeLabel(message.created_at)}{message.edited_at ? " · Edited" : ""}</p></div></div>;
}
