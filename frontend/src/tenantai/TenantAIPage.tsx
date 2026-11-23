import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, KeyRound, LoaderCircle, ShieldCheck, Trash2 } from "lucide-react";
import { ApiError } from "../auth/api";
import { CustomerErrorBanner, CustomerPageHeader } from "../customers/CustomerUi";
import {
  formatDateTime,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
} from "../admin/sales/salesBookingUi";
import { clearProvider, fetchProvider, saveProvider, tenantAIKeys } from "./api";
import { providerLabel, validateProviderInput } from "./model";
import type { AIProviderName } from "./model";

export function TenantAIPage() {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<AIProviderName>("groq");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [formError, setFormError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const query = useQuery({
    queryKey: tenantAIKeys.provider,
    queryFn: fetchProvider,
    retry: (count, error: unknown) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
  const notConfigured = query.error instanceof ApiError && query.error.status === 404;
  const save = useMutation({
    mutationFn: saveProvider,
    onSuccess: async (saved) => {
      setApiKey(""); setFormError(null); setNotice("AI provider saved. The key is encrypted and cannot be read back.");
      setProvider(saved.provider === "groq" ? "groq" : "openai-compatible");
      setModel(saved.model); setBaseUrl(saved.base_url ?? "");
      await queryClient.invalidateQueries({ queryKey: tenantAIKeys.provider });
    },
    onError: setFormError,
  });
  const clear = useMutation({
    mutationFn: clearProvider,
    onSuccess: async () => {
      setApiKey(""); setFormError(null); setNotice("Organization AI provider cleared. Central assistant settings will be used.");
      await queryClient.invalidateQueries({ queryKey: tenantAIKeys.provider });
    },
    onError: setFormError,
  });

  const submit = () => {
    setNotice(null);
    const validation = validateProviderInput({ provider, apiKey, model, baseUrl });
    if (validation) { setFormError(new Error(validation)); return; }
    setFormError(null);
    save.mutate({ provider, api_key: apiKey.trim(), model: model.trim(), base_url: provider === "openai-compatible" ? baseUrl.trim() : null });
  };
  const current = query.data;

  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Settings" title="AI providers" description="Connect your organization's own Groq or OpenAI-compatible endpoint for tenant AI features." />
    {notice && <p role="status" className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><CheckCircle2 className="size-4" />{notice}</p>}
    <div className="grid gap-6 lg:grid-cols-[1fr_0.85fr]">
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-forest/10 text-forest"><Bot className="size-5" /></span><div><h2 className="font-semibold">Provider connection</h2><p className="mt-0.5 text-xs text-charcoal/55">Saving replaces the active organization provider.</p></div></div>
        <form className="mt-6 space-y-4" onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <CustomerErrorBanner error={formError} fallback="The provider could not be saved." />
          <label className={saleLabelClasses}>Provider<select className={saleInputClasses} value={provider} onChange={(event) => setProvider(event.target.value as AIProviderName)}><option value="groq">Groq</option><option value="openai-compatible">OpenAI-compatible</option></select></label>
          {provider === "openai-compatible" && <label className={saleLabelClasses}>Base URL<input required type="url" maxLength={500} className={saleInputClasses} value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" /></label>}
          <label className={saleLabelClasses}>Model name<input required maxLength={128} className={saleInputClasses} value={model} onChange={(event) => setModel(event.target.value)} placeholder={provider === "groq" ? "llama-3.3-70b-versatile" : "your-model-name"} /></label>
          <label className={saleLabelClasses}>API key<div className="relative"><KeyRound className="pointer-events-none absolute left-3 top-4 size-4 text-charcoal/35" /><input required minLength={8} maxLength={4096} type="password" autoComplete="new-password" className={`${saleInputClasses} pl-9`} value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Enter a new key" /></div></label>
          <p className="text-xs leading-5 text-charcoal/55">A new key is required to replace a connection. It is sent only to this provider endpoint, encrypted at rest, cleared from this form after saving, and never returned by the API.</p>
          <button type="submit" disabled={save.isPending} className={salePrimaryButton}>{save.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}Save provider</button>
        </form>
      </section>
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <h2 className="font-semibold">Current configuration</h2>
        {query.isLoading && <p role="status" className="mt-6 flex items-center gap-2 text-sm text-charcoal/60"><LoaderCircle className="size-4 animate-spin" />Reading masked configuration…</p>}
        {notConfigured && <div className="mt-6 rounded-xl border border-dashed border-charcoal/20 p-5 text-sm leading-6 text-charcoal/60">No organization provider is configured. Tenant AI features use the centrally managed settings.</div>}
        {query.isError && !notConfigured && <div className="mt-4"><CustomerErrorBanner error={query.error} fallback="The provider configuration could not be loaded." onRetry={() => void query.refetch()} /></div>}
        {current && <div className="mt-5 space-y-4 text-sm"><dl className="space-y-3"><div><dt className="text-xs text-charcoal/50">Provider</dt><dd className="mt-1 font-medium">{providerLabel(current.provider)}</dd></div><div><dt className="text-xs text-charcoal/50">Model</dt><dd className="mt-1 break-words font-mono text-xs">{current.model}</dd></div>{current.base_url && <div><dt className="text-xs text-charcoal/50">Base URL</dt><dd className="mt-1 break-all text-xs">{current.base_url}</dd></div>}<div><dt className="text-xs text-charcoal/50">API key</dt><dd className="mt-1 font-mono tracking-wider">{current.api_key_masked}</dd></div><div><dt className="text-xs text-charcoal/50">Last updated</dt><dd className="mt-1 text-xs">{formatDateTime(current.updated_at)}</dd></div></dl><span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-800">{current.is_active ? "ACTIVE" : "INACTIVE"}</span><button type="button" disabled={clear.isPending} className="flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 px-3 py-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50" onClick={() => { if (window.confirm("Clear this organization's AI provider? Central settings will be used instead.")) { setNotice(null); clear.mutate(); } }}>{clear.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}Clear provider</button></div>}
      </section>
    </div>
  </div>;
}
