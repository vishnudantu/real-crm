import { useEffect, useRef, useState } from "react";
import { Check, Code2, Copy, ExternalLink, LoaderCircle, MonitorSmartphone } from "lucide-react";
import { fetchEmbedSnippet } from "./api";
import { errorMessage } from "../shared/apiRequest";
import type { EmbedSnippet } from "./omnichannelModel";

export function WebsiteWidgetInstaller() {
  const [embed, setEmbed] = useState<EmbedSnippet | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const resetCopyTimer = useRef<number | null>(null);

  const loadSnippet = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setEmbed(await fetchEmbedSnippet());
    } catch (reason: unknown) {
      setError(errorMessage(reason, "The widget installation snippet is unavailable."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadSnippet();
    return () => {
      if (resetCopyTimer.current !== null) window.clearTimeout(resetCopyTimer.current);
    };
  }, []);

  const copySnippet = async () => {
    if (!embed?.snippet) return;
    try {
      await navigator.clipboard.writeText(embed.snippet);
      setCopied(true);
      if (resetCopyTimer.current !== null) window.clearTimeout(resetCopyTimer.current);
      resetCopyTimer.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Clipboard access was blocked by the browser. Select the snippet and copy it manually.");
    }
  };

  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
      <div className="flex items-start gap-3 border-b border-charcoal/10 pb-5">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-charcoal text-ivory"><Code2 aria-hidden="true" className="size-5" /></span>
        <div><h2 className="text-base font-semibold text-charcoal">Website chat & lead-capture widget</h2><p className="mt-1 text-xs leading-5 text-charcoal/55">Bring branded chat and consented enquiries from your website into the omnichannel inbox.</p></div>
      </div>

      {error && <div role="alert" className="mt-5 flex flex-col gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700 sm:flex-row sm:items-center sm:justify-between"><span>{error}</span><button type="button" onClick={() => void loadSnippet()} className="shrink-0 font-semibold underline underline-offset-2">Try again</button></div>}
      {isLoading ? (
        <div role="status" className="flex min-h-36 items-center justify-center gap-2 text-xs text-charcoal/50"><LoaderCircle aria-hidden="true" className="size-4 animate-spin" />Loading your tenant installation snippet…</div>
      ) : embed?.enabled && embed.snippet ? (
        <>
          <div className="mt-5"><div className="flex items-center justify-between gap-3"><h3 className="text-xs font-semibold">Your tenant snippet</h3><button type="button" onClick={() => void copySnippet()} className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-xl bg-charcoal px-3.5 py-2 text-xs font-semibold text-ivory transition-colors hover:bg-charcoal/90">{copied ? <Check aria-hidden="true" className="size-3.5" /> : <Copy aria-hidden="true" className="size-3.5" />}{copied ? "Copied" : "Copy snippet"}</button></div><pre className="mt-2 overflow-x-auto rounded-xl border border-charcoal/10 bg-charcoal p-4 text-xs leading-6 whitespace-pre-wrap break-all text-ivory"><code>{embed.snippet}</code></pre>{embed.installation && <p className="mt-2 text-xs leading-5 text-charcoal/55">{embed.installation}</p>}</div>

          <div className="mt-6 grid gap-5 border-t border-charcoal/10 pt-5 md:grid-cols-[1fr_auto] md:items-end">
            <div><h3 className="text-xs font-semibold">Install in three steps</h3><ol className="mt-3 space-y-3">{["Copy the snippet above.", "Paste it before the closing </body> tag on your website.", "Publish your site and open the demo to verify chat and lead capture."].map((step, index) => <li key={step} className="flex items-start gap-2.5 text-xs leading-5 text-charcoal/65"><span className="grid size-5 shrink-0 place-items-center rounded-full bg-charcoal/5 text-[0.65rem] font-semibold text-charcoal">{index + 1}</span>{step}</li>)}</ol></div>
            <a href="/demo-widget.html" target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-charcoal/15 px-4 py-2 text-xs font-semibold text-charcoal transition-colors hover:bg-charcoal/5"><MonitorSmartphone aria-hidden="true" className="size-4" />Preview demo website<ExternalLink aria-hidden="true" className="size-3.5 text-charcoal/45" /></a>
          </div>
          {embed.embed_url && <a href={embed.embed_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-sky-800 hover:underline">Inspect hosted embed script<ExternalLink aria-hidden="true" className="size-3" /></a>}
        </>
      ) : !error ? (
        <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">The website widget is not enabled for this organization. Ask your PropFlow operator to enable it.</p>
      ) : null}
    </section>
  );
}
