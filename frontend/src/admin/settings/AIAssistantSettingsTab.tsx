import { useState } from "react";
import type { FormEvent } from "react";
import { Bot, Save } from "lucide-react";
import type { AIAssistantSettings, UpdateAIAssistantSettingsPayload } from "../settingsModel";

interface AIAssistantSettingsTabProps {
  aiSettings: AIAssistantSettings;
  onUpdateAI: (payload: UpdateAIAssistantSettingsPayload) => Promise<void>;
  isSaving: boolean;
}

export function AIAssistantSettingsTab({ aiSettings, onUpdateAI, isSaving }: AIAssistantSettingsTabProps) {
  const [groundingMode, setGroundingMode] = useState(aiSettings.grounding_mode);
  const [temperature, setTemperature] = useState(aiSettings.default_temperature);
  const [maxTokens, setMaxTokens] = useState(aiSettings.max_response_tokens);
  const [autoDetect, setAutoDetect] = useState(aiSettings.multilingual_auto_detect);
  const [fallbackReply, setFallbackReply] = useState(aiSettings.fallback_reply);
  const [unconfiguredReply, setUnconfiguredReply] = useState(aiSettings.unconfigured_project_reply);

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onUpdateAI({
      grounding_mode: groundingMode,
      default_temperature: Number(temperature),
      max_response_tokens: Number(maxTokens),
      multilingual_auto_detect: autoDetect,
      fallback_reply: fallbackReply.trim(),
      unconfigured_project_reply: unconfiguredReply.trim(),
    });
  };

  return (
    <form onSubmit={(event) => void handleSave(event)} className="flex flex-col gap-6">
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <div className="flex items-center gap-2 border-b border-charcoal/10 pb-4"><Bot aria-hidden="true" className="size-4 text-charcoal" /><h2 className="text-base font-semibold text-charcoal">AI grounding & generation</h2></div>
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <fieldset><legend className="mb-3 text-xs font-semibold text-charcoal/70">Approved fact sheet grounding mode</legend><div className="space-y-2">
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-charcoal/15 p-3 hover:border-charcoal/30"><input type="radio" name="grounding_mode" checked={groundingMode === "STRICT_FACTS_ONLY"} onChange={() => setGroundingMode("STRICT_FACTS_ONLY")} className="mt-0.5 size-4" /><span className="text-xs"><span className="block font-semibold">Strict facts only</span><span className="mt-1 block leading-5 text-charcoal/60">Restrict responses to verified project fact sheets. Never guess amenities, pricing or dates.</span></span></label>
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-charcoal/15 p-3 hover:border-charcoal/30"><input type="radio" name="grounding_mode" checked={groundingMode === "BALANCED"} onChange={() => setGroundingMode("BALANCED")} className="mt-0.5 size-4" /><span className="text-xs"><span className="block font-semibold">Balanced advisory</span><span className="mt-1 block leading-5 text-charcoal/60">Keep answers grounded in facts while allowing warmer conversational transitions and developer context.</span></span></label>
          </div></fieldset>
          <div className="space-y-5 text-xs">
            <div><div className="flex items-center justify-between gap-3"><label htmlFor="ai-temperature" className="font-semibold text-charcoal/70">Temperature ({temperature})</label><span className="text-[0.68rem] text-charcoal/45">{temperature <= 0.2 ? "Precise & deterministic" : "More creative"}</span></div><input id="ai-temperature" aria-label="AI response temperature" type="range" min="0.0" max="0.8" step="0.05" value={temperature} onChange={(event) => setTemperature(Number(event.target.value))} className="mt-3 w-full accent-charcoal" /></div>
            <label className="block font-semibold text-charcoal/70">Maximum response tokens<input type="number" min="200" max="1200" step="50" value={maxTokens} onChange={(event) => setMaxTokens(Number(event.target.value))} className="mt-2 w-full rounded-xl border border-charcoal/15 px-3 py-2.5 text-xs font-normal text-charcoal outline-none focus:border-charcoal/45" /></label>
            <label className="flex items-center gap-2 font-semibold text-charcoal/70"><input type="checkbox" checked={autoDetect} onChange={(event) => setAutoDetect(event.target.checked)} className="size-4" />Automatically detect and match buyer language</label>
          </div>
        </div>
        <div className="mt-6 grid gap-5 border-t border-charcoal/10 pt-5 text-xs md:grid-cols-2">
          <label className="block font-semibold text-charcoal/70">Standard fallback reply<textarea rows={4} value={fallbackReply} onChange={(event) => setFallbackReply(event.target.value)} className="mt-2 w-full rounded-xl border border-charcoal/15 px-3 py-2.5 font-normal leading-5 text-charcoal outline-none focus:border-charcoal/45" /><span className="mt-1 block font-normal text-charcoal/45">Used when approved facts are unavailable.</span></label>
          <label className="block font-semibold text-charcoal/70">Unconfigured project reply<textarea rows={4} value={unconfiguredReply} onChange={(event) => setUnconfiguredReply(event.target.value)} className="mt-2 w-full rounded-xl border border-charcoal/15 px-3 py-2.5 font-normal leading-5 text-charcoal outline-none focus:border-charcoal/45" /><span className="mt-1 block font-normal text-charcoal/45">Used when a project has no published facts yet.</span></label>
        </div>
      </section>
      <div className="flex justify-end"><button type="submit" disabled={isSaving} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-charcoal px-5 py-2.5 text-xs font-semibold text-ivory hover:bg-charcoal/90 disabled:opacity-50"><Save aria-hidden="true" className="size-4" />{isSaving ? "Saving…" : "Save AI settings"}</button></div>
    </form>
  );
}
