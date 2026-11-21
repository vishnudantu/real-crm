import {
  Camera,
  Globe,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  Send,
} from "lucide-react";
import type { ChannelType } from "./omnichannelModel";

const CHANNEL_META: Record<
  ChannelType,
  { label: string; short: string; className: string; Icon: typeof Globe }
> = {
  WEB_CHAT: {
    label: "Website chat",
    short: "Web",
    className: "bg-sky-50 text-sky-700 border-sky-200",
    Icon: Globe,
  },
  WHATSAPP: {
    label: "WhatsApp",
    short: "WA",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    Icon: MessageCircle,
  },
  INSTAGRAM: {
    label: "Instagram",
    short: "IG",
    className: "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200",
    Icon: Camera,
  },
  MESSENGER: {
    label: "Messenger",
    short: "FB",
    className: "bg-blue-50 text-blue-700 border-blue-200",
    Icon: Send,
  },
  SMS: {
    label: "SMS",
    short: "SMS",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    Icon: MessageSquare,
  },
  EMAIL: {
    label: "Email",
    short: "Mail",
    className: "bg-slate-50 text-slate-700 border-slate-200",
    Icon: Mail,
  },
  VOICE: {
    label: "Voice call",
    short: "Call",
    className: "bg-violet-50 text-violet-700 border-violet-200",
    Icon: Phone,
  },
};

export function ChannelBadge({ channel }: { channel: ChannelType }) {
  const meta = CHANNEL_META[channel] ?? CHANNEL_META.WEB_CHAT;
  const Icon = meta.Icon;
  return (
    <span
      title={meta.label}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.66rem] font-semibold ${meta.className}`}
    >
      <Icon aria-hidden="true" className="size-3" />
      {meta.short}
    </span>
  );
}

export { CHANNEL_META };
