import { useEffect, useState } from "react";
import {
  Camera,
  LoaderCircle,
  MessageCircle,
  Plug,
  Save,
  Send,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  configureChannel,
  fetchChannelCredentials,
} from "./api";
import { errorMessage } from "../shared/apiRequest";
import type {
  ChannelCredentialSummary,
  ChannelType,
} from "./omnichannelModel";
import { WebsiteWidgetInstaller } from "./WebsiteWidgetInstaller";

interface ChannelFormState {
  provider: string;
  access_token: string;
  app_secret: string;
  page_id: string;
  phone_number_id: string;
  graph_base_url: string;
  ws_url: string;
  api_key: string;
  api_secret: string;
}

const EMPTY_FORM: ChannelFormState = {
  provider: "meta",
  access_token: "",
  app_secret: "",
  page_id: "",
  phone_number_id: "",
  graph_base_url: "",
  ws_url: "",
  api_key: "",
  api_secret: "",
};

const CHANNEL_SECTIONS: {
  channel: ChannelType;
  title: string;
  description: string;
  Icon: typeof MessageCircle;
  fields: { key: keyof ChannelFormState; label: string; secret?: boolean; placeholder: string }[];
}[] = [
  {
    channel: "WHATSAPP",
    title: "WhatsApp Cloud API",
    description:
      "Official Meta WhatsApp Business. Incoming messages arrive via your tenant webhook; replies use your Page access token.",
    Icon: MessageCircle,
    fields: [
      { key: "access_token", label: "Page access token", secret: true, placeholder: "EAAG…" },
      { key: "app_secret", label: "Meta app secret (for webhook signatures)", secret: true, placeholder: "App secret" },
      { key: "phone_number_id", label: "Phone number ID", placeholder: "123456789012345" },
    ],
  },
  {
    channel: "INSTAGRAM",
    title: "Instagram DMs",
    description:
      "Instagram professional account messaging via the Meta Graph API.",
    Icon: Camera,
    fields: [
      { key: "access_token", label: "Page access token", secret: true, placeholder: "EAAG…" },
      { key: "app_secret", label: "Meta app secret", secret: true, placeholder: "App secret" },
      { key: "page_id", label: "Instagram-linked Page ID", placeholder: "Page ID" },
    ],
  },
  {
    channel: "MESSENGER",
    title: "Facebook Messenger",
    description:
      "Page inbox conversations through the Messenger Send API.",
    Icon: Send,
    fields: [
      { key: "access_token", label: "Page access token", secret: true, placeholder: "EAAG…" },
      { key: "app_secret", label: "Meta app secret", secret: true, placeholder: "App secret" },
      { key: "page_id", label: "Facebook Page ID", placeholder: "Page ID" },
    ],
  },
  {
    channel: "VOICE",
    title: "Browser calling (LiveKit)",
    description:
      "Self-hosted or LiveKit Cloud server for in-app audio calls and Egress recordings. Choose 'simulated' to test without a media server.",
    Icon: Plug,
    fields: [
      { key: "ws_url", label: "LiveKit WebSocket URL", placeholder: "wss://your-livekit.example.com" },
      { key: "api_key", label: "LiveKit API key", secret: true, placeholder: "API…" },
      { key: "api_secret", label: "LiveKit API secret", secret: true, placeholder: "Secret" },
    ],
  },
];

export function ChannelsSettingsPage() {
  const [existing, setExisting] = useState<ChannelCredentialSummary[]>([]);
  const [forms, setForms] = useState<Record<string, ChannelFormState>>({});
  const [verifyToken, setVerifyToken] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchChannelCredentials()
      .then((rows) => {
        setExisting(rows);
        const next: Record<string, ChannelFormState> = {};
        for (const row of rows) {
          next[row.channel] = {
            ...EMPTY_FORM,
            provider: row.provider,
            page_id: String(row.config.page_id ?? ""),
            phone_number_id: String(row.config.phone_number_id ?? ""),
            graph_base_url: String(row.config.graph_base_url ?? ""),
            ws_url: String(row.config.ws_url ?? ""),
          };
        }
        setForms(next);
      })
      .catch((err) => setError(errorMessage(err, "Channel configuration is unavailable.")));
  }, []);

  const formFor = (channel: string): ChannelFormState => forms[channel] ?? EMPTY_FORM;

  const updateField = (channel: string, key: keyof ChannelFormState, value: string) => {
    setForms((current) => ({
      ...current,
      [channel]: { ...(current[channel] ?? EMPTY_FORM), [key]: value },
    }));
  };

  const save = async (channel: ChannelType) => {
    setSaving(channel);
    setMessage(null);
    setError(null);
    const form = formFor(channel);
    try {
      const credentials: Record<string, string> = {};
      if (form.access_token) credentials.access_token = form.access_token;
      if (form.app_secret) credentials.app_secret = form.app_secret;
      if (form.api_key) credentials.api_key = form.api_key;
      if (form.api_secret) credentials.api_secret = form.api_secret;

      const config: Record<string, unknown> = {};
      if (form.page_id) config.page_id = form.page_id;
      if (form.phone_number_id) config.phone_number_id = form.phone_number_id;
      if (form.graph_base_url) config.graph_base_url = form.graph_base_url;
      if (form.ws_url) config.ws_url = form.ws_url;
      if (form.provider === "simulated") config.allow_unsigned_simulation = false;

      await configureChannel(channel, {
        channel,
        provider: form.provider,
        credentials,
        config,
        is_active: true,
        ...(verifyToken[channel] ? { webhook_verify_token: verifyToken[channel] } : {}),
      });
      setMessage(`${channel} configuration saved. Credentials are stored encrypted.`);
      setForms((current) => ({
        ...current,
        [channel]: { ...current[channel], access_token: "", app_secret: "", api_key: "", api_secret: "" },
      }));
    } catch (err) {
      setError(errorMessage(err, "Saving the channel failed."));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-charcoal">Channels & website widget</h1>
        <p className="text-sm text-charcoal/60">
          Connect WhatsApp, Instagram, Messenger and LiveKit calling. Secrets are encrypted per organization.
        </p>
      </header>

      {message && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}

      <WebsiteWidgetInstaller />

      <div className="flex justify-end">
        <Link to="/admin/settings/widget" className="text-xs font-semibold text-sky-800 hover:underline">Open widget installation guide</Link>
      </div>

      {CHANNEL_SECTIONS.map((section) => {
        const form = formFor(section.channel);
        const Icon = section.Icon;
        const isConfigured = existing.some((row) => row.channel === section.channel && row.is_active);
        return (
          <section key={section.channel} className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Icon aria-hidden="true" className="size-5 text-charcoal/70" />
                <h2 className="text-base font-semibold text-charcoal">{section.title}</h2>
              </div>
              {isConfigured && (
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[0.68rem] font-semibold text-emerald-700">
                  Configured
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-charcoal/60">{section.description}</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-charcoal/70">
                Provider
                <select
                  value={form.provider}
                  onChange={(event) => updateField(section.channel, "provider", event.target.value)}
                  className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
                >
                  {section.channel === "VOICE" ? (
                    <>
                      <option value="simulated">Simulated (no media server)</option>
                      <option value="livekit">LiveKit (self-hosted / Cloud)</option>
                    </>
                  ) : (
                    <>
                      <option value="meta">Meta Graph API (live)</option>
                      <option value="simulated">Simulated (development)</option>
                    </>
                  )}
                </select>
              </label>
              {section.fields.map((field) => (
                <label key={field.key} className="text-xs font-semibold text-charcoal/70">
                  {field.label}
                  <input
                    type={field.secret ? "password" : "text"}
                    value={form[field.key]}
                    placeholder={field.placeholder}
                    autoComplete="off"
                    onChange={(event) => updateField(section.channel, field.key, event.target.value)}
                    className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
                  />
                </label>
              ))}
              {section.channel !== "VOICE" && (
                <label className="text-xs font-semibold text-charcoal/70 sm:col-span-2">
                  Webhook verify token (choose any secret string; enter the same value in the Meta developer console)
                  <input
                    type="password"
                    value={verifyToken[section.channel] ?? ""}
                    onChange={(event) =>
                      setVerifyToken((current) => ({ ...current, [section.channel]: event.target.value }))
                    }
                    placeholder="A random string you control"
                    autoComplete="off"
                    className="mt-1 w-full rounded-lg border border-charcoal/15 px-3 py-2 text-sm font-normal"
                  />
                </label>
              )}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => void save(section.channel)}
                disabled={saving === section.channel}
                className="inline-flex items-center gap-2 rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory disabled:opacity-50"
              >
                {saving === section.channel ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Save aria-hidden="true" className="size-4" />
                )}
                Save {section.channel === "VOICE" ? "calling" : section.channel.toLowerCase()} settings
              </button>
              <p className="text-[0.68rem] text-charcoal/45">
                Secrets are never returned by the API after saving.
              </p>
            </div>
          </section>
        );
      })}
    </div>
  );
}
