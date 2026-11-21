import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCheck,
  Inbox,
  LoaderCircle,
  MessageSquare,
  Phone,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";
import { ChannelBadge } from "./ChannelBadge";
import {
  fetchConversation,
  fetchInbox,
  joinCall,
  sendChannelReply,
  startCall,
} from "./api";
import { errorMessage } from "../shared/apiRequest";
import type {
  CallRecord,
  ChannelConversation,
  ChannelConversationDetail,
  ChannelMessage,
  ChannelType,
} from "./omnichannelModel";
import { CallingPanel } from "./CallingPanel";

const CHANNEL_TABS: { value: ChannelType | ""; label: string }[] = [
  { value: "", label: "All channels" },
  { value: "WHATSAPP", label: "WhatsApp" },
  { value: "INSTAGRAM", label: "Instagram" },
  { value: "MESSENGER", label: "Messenger" },
  { value: "WEB_CHAT", label: "Website" },
];

const REFRESH_INTERVAL_MS = 15_000;

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const delta = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(delta / 60_000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function initials(name: string | null, handle: string | null): string {
  const source = name?.trim() || handle || "?";
  return source
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function displayName(conversation: ChannelConversation): string {
  return (
    conversation.contact_name?.trim() ||
    conversation.contact_handle?.trim() ||
    "Unknown contact"
  );
}

export function OmnichannelInboxPage() {
  const [channelFilter, setChannelFilter] = useState<ChannelType | "">("");
  const [query, setQuery] = useState("");
  const [inbox, setInbox] = useState<ChannelConversation[]>([]);
  const [unreadTotal, setUnreadTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChannelConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [activeCall, setActiveCall] = useState<CallRecord | null>(null);
  const [callError, setCallError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadInbox = useCallback(async () => {
    try {
      const data = await fetchInbox({ channel: channelFilter || undefined, limit: 100 });
      setInbox(data.items);
      setUnreadTotal(data.unread_total);
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load the inbox."));
    } finally {
      setLoading(false);
    }
  }, [channelFilter]);

  const openConversation = useCallback(async (id: string) => {
    setSelectedId(id);
    setThreadLoading(true);
    setActiveCall(null);
    try {
      const data = await fetchConversation(id);
      setDetail(data);
    } catch (err) {
      setError(errorMessage(err, "Could not open the conversation."));
    } finally {
      setThreadLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInbox();
    const interval = window.setInterval(loadInbox, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [loadInbox]);

  useEffect(() => {
    if (!selectedId) return;
    const interval = window.setInterval(() => {
      void fetchConversation(selectedId).then(setDetail).catch(() => undefined);
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [selectedId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [detail?.messages.length]);

  const filtered = useMemo(() => {
    if (!query.trim()) return inbox;
    const needle = query.toLowerCase();
    return inbox.filter((item) =>
      `${item.contact_name ?? ""} ${item.contact_handle ?? ""} ${item.last_message_preview ?? ""}`
        .toLowerCase()
        .includes(needle),
    );
  }, [inbox, query]);

  const sendReply = async () => {
    if (!detail || !reply.trim() || sending) return;
    setSending(true);
    try {
      const message: ChannelMessage = await sendChannelReply(detail.id, reply.trim());
      setDetail((current) =>
        current
          ? { ...current, messages: [...current.messages, message], unread_count: 0 }
          : current,
      );
      setReply("");
      void loadInbox();
    } catch (err) {
      setError(errorMessage(err, "Reply could not be sent."));
    } finally {
      setSending(false);
    }
  };

  const beginCall = async () => {
    if (!detail) return;
    setCallError(null);
    try {
      const started = await startCall({
        conversation_id: detail.id,
        destination: detail.contact_handle ?? undefined,
      });
      setActiveCall(started.call);
      // Immediately join so the agent is connected in one click.
      await joinCall(started.call.id);
    } catch (err) {
      setCallError(errorMessage(err, "The call could not be started."));
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center gap-3 text-charcoal/70">
        <LoaderCircle className="size-5 animate-spin" />
        Loading omnichannel inbox…
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-charcoal">
            <Inbox aria-hidden="true" className="size-5" />
            Omnichannel inbox
            {unreadTotal > 0 && (
              <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[0.7rem] font-bold text-white">
                {unreadTotal} unread
              </span>
            )}
          </h1>
          <p className="text-sm text-charcoal/60">
            WhatsApp, Instagram, Messenger and website chats in one place.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadInbox()}
          className="inline-flex items-center gap-2 rounded-lg border border-charcoal/15 px-3 py-2 text-xs font-semibold text-charcoal/70 hover:bg-charcoal/5"
        >
          <RefreshCw aria-hidden="true" className="size-4" />
          Refresh
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        {/* Thread list pane */}
        <section className="flex w-full max-w-sm flex-col rounded-2xl border border-charcoal/10 bg-white shadow-xs">
          <div className="flex gap-1 overflow-x-auto border-b border-charcoal/10 p-2">
            {CHANNEL_TABS.map((tab) => (
              <button
                key={tab.value || "all"}
                type="button"
                onClick={() => setChannelFilter(tab.value)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-colors ${
                  channelFilter === tab.value
                    ? "bg-charcoal text-ivory"
                    : "text-charcoal/65 hover:bg-charcoal/5"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="border-b border-charcoal/10 p-2">
            <div className="flex items-center gap-2 rounded-lg border border-charcoal/10 px-3 py-2">
              <Search aria-hidden="true" className="size-4 text-charcoal/40" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search contacts or messages…"
                className="w-full bg-transparent text-sm outline-none placeholder:text-charcoal/40"
              />
            </div>
          </div>
          <ul className="min-h-0 flex-1 overflow-y-auto">
            {filtered.length === 0 && (
              <li className="flex flex-col items-center gap-2 px-6 py-16 text-center text-sm text-charcoal/55">
                <MessageSquare aria-hidden="true" className="size-8 text-charcoal/25" />
                No conversations yet.
                <span className="text-xs">
                  Inbound WhatsApp, Instagram and website chats will appear here automatically.
                </span>
              </li>
            )}
            {filtered.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => void openConversation(item.id)}
                  className={`flex w-full items-start gap-3 border-b border-charcoal/5 px-3 py-3 text-left transition-colors ${
                    selectedId === item.id ? "bg-charcoal/5" : "hover:bg-charcoal/[0.03]"
                  }`}
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-charcoal/10 text-xs font-bold text-charcoal">
                    {initials(item.contact_name, item.contact_handle)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-charcoal">
                        {displayName(item)}
                      </span>
                      <span className="shrink-0 text-[0.68rem] text-charcoal/50">
                        {relativeTime(item.last_message_at)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <ChannelBadge channel={item.channel} />
                      <span className="truncate text-xs text-charcoal/60">
                        {item.last_message_preview ?? "No messages yet"}
                      </span>
                    </div>
                  </div>
                  {item.unread_count > 0 && (
                    <span className="grid size-5 shrink-0 place-items-center rounded-full bg-emerald-500 text-[0.66rem] font-bold text-white">
                      {item.unread_count}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* Conversation pane */}
        <section className="hidden min-w-0 flex-1 flex-col rounded-2xl border border-charcoal/10 bg-white shadow-xs md:flex">
          {!detail && !threadLoading && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-charcoal/55">
              <MessageSquare aria-hidden="true" className="size-12 text-charcoal/20" />
              <p className="text-sm">Select a conversation to start replying.</p>
            </div>
          )}

          {threadLoading && (
            <div className="flex flex-1 items-center justify-center text-charcoal/60">
              <LoaderCircle className="size-6 animate-spin" />
            </div>
          )}

          {detail && !threadLoading && (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-charcoal/10 px-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-charcoal text-xs font-bold text-ivory">
                    {initials(detail.contact_name, detail.contact_handle)}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-charcoal">
                      {displayName(detail)}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-charcoal/55">
                      <ChannelBadge channel={detail.channel} />
                      {detail.contact_handle && <span className="truncate">{detail.contact_handle}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={beginCall}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                  >
                    <Phone aria-hidden="true" className="size-4" />
                    Call
                  </button>
                </div>
              </div>

              {callError && (
                <p className="border-b border-rose-100 bg-rose-50 px-4 py-2 text-xs text-rose-700">
                  {callError}
                </p>
              )}
              {activeCall && (
                <CallingPanel
                  call={activeCall}
                  onEnded={(ended) => setActiveCall(ended)}
                />
              )}

              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-[#FAFAF7] px-4 py-4">
                {detail.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
                <div ref={messagesEndRef} />
              </div>

              <div className="border-t border-charcoal/10 p-3">
                <div className="flex items-end gap-2">
                  <textarea
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void sendReply();
                      }
                    }}
                    rows={2}
                    placeholder={`Reply on ${detail.channel === "WHATSAPP" ? "WhatsApp" : detail.channel === "INSTAGRAM" ? "Instagram" : detail.channel === "MESSENGER" ? "Messenger" : "web chat"}…`}
                    className="flex-1 resize-none rounded-xl border border-charcoal/15 px-3 py-2 text-sm outline-none focus:border-charcoal/40"
                  />
                  <button
                    type="button"
                    onClick={() => void sendReply()}
                    disabled={sending || !reply.trim()}
                    className="inline-flex size-11 items-center justify-center rounded-xl bg-charcoal text-ivory transition-opacity disabled:opacity-40"
                    aria-label="Send reply"
                  >
                    {sending ? (
                      <LoaderCircle className="size-5 animate-spin" />
                    ) : (
                      <Send aria-hidden="true" className="size-5" />
                    )}
                  </button>
                </div>
                <p className="mt-1.5 flex items-center gap-1 text-[0.68rem] text-charcoal/45">
                  <CheckCheck aria-hidden="true" className="size-3" />
                  Enter to send · Shift+Enter for a new line · delivered via the tenant's configured provider
                </p>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChannelMessage }) {
  const outbound = message.direction === "OUTBOUND";
  return (
    <div className={`flex ${outbound ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-3.5 py-2.5 text-sm shadow-xs ${
          outbound
            ? "rounded-br-sm bg-charcoal text-ivory"
            : "rounded-bl-sm border border-charcoal/10 bg-white text-charcoal"
        }`}
      >
        {message.content && <p className="whitespace-pre-wrap break-words">{message.content}</p>}
        {message.media_url && !message.content && (
          <a
            href={message.media_url}
            target="_blank"
            rel="noreferrer"
            className={`text-xs underline ${outbound ? "text-ivory/90" : "text-sky-700"}`}
          >
            View {message.content_type.toLowerCase()} attachment
          </a>
        )}
        <div
          className={`mt-1 flex items-center justify-end gap-1.5 text-[0.66rem] ${
            outbound ? "text-ivory/60" : "text-charcoal/45"
          }`}
        >
          {message.status === "FAILED" && <span className="font-semibold text-rose-400">Failed</span>}
          <span>{relativeTime(message.created_at)}</span>
          {outbound && <CheckCheck aria-hidden="true" className="size-3" />}
        </div>
      </div>
    </div>
  );
}
