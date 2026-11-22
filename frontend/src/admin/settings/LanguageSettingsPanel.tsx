import { useState } from "react";
import type { FormEvent } from "react";
import { Globe, Save } from "lucide-react";
import type { LanguageItem, LanguageSettings, UpdateLanguageSettingsPayload } from "../settingsModel";

interface LanguageSettingsPanelProps {
  langSettings: LanguageSettings;
  onUpdateLanguages: (payload: UpdateLanguageSettingsPayload) => Promise<void>;
  isSaving: boolean;
}

export function LanguageSettingsPanel({ langSettings, onUpdateLanguages, isSaving }: LanguageSettingsPanelProps) {
  const [languages, setLanguages] = useState<LanguageItem[]>(langSettings.languages.map((language) => ({ ...language })));

  const toggleLanguageEnabled = (code: string) => {
    setLanguages((current) => current.map((language) => language.code === code ? { ...language, is_enabled: !language.is_enabled } : language));
  };

  const setDefaultLanguage = (code: string) => {
    setLanguages((current) => current.map((language) => ({ ...language, is_default: language.code === code, is_enabled: language.code === code ? true : language.is_enabled })));
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onUpdateLanguages({ languages });
  };

  return (
    <form onSubmit={(event) => void save(event)} className="space-y-6">
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-charcoal/10 pb-4"><div className="flex items-center gap-2"><Globe aria-hidden="true" className="size-4 text-charcoal" /><h2 className="text-base font-semibold text-charcoal">Buyer conversation languages</h2></div><span className="rounded-full bg-charcoal/5 px-2.5 py-1 text-xs font-medium text-charcoal/65">{languages.filter((language) => language.is_enabled).length} active languages</span></div>
        <p className="mt-4 text-xs leading-5 text-charcoal/55">Choose which languages your AI assistant and sales team can use. The default language is always enabled.</p>
        <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[500px] text-left text-xs"><thead><tr className="border-b border-charcoal/10 text-[0.65rem] font-semibold tracking-wider text-charcoal/50 uppercase"><th className="pb-3 pl-1">Language</th><th className="pb-3">Native script</th><th className="pb-3 text-center">Default</th><th className="pb-3 pr-1 text-right">Enabled</th></tr></thead><tbody className="divide-y divide-charcoal/5">{languages.map((language) => <tr key={language.code} className="hover:bg-charcoal/[0.02]"><td className="py-3 pl-1 font-semibold">{language.name}<span className="ml-2 font-mono text-[0.65rem] font-normal text-charcoal/40 uppercase">({language.code})</span></td><td className="py-3 text-charcoal/70">{language.native_name}</td><td className="py-3 text-center"><input type="radio" name="default_language" aria-label={`Set ${language.name} as default`} checked={language.is_default} onChange={() => setDefaultLanguage(language.code)} className="size-4 cursor-pointer" /></td><td className="py-3 pr-1 text-right"><label className="relative inline-flex cursor-pointer items-center"><input type="checkbox" aria-label={`Enable ${language.name}`} checked={language.is_enabled} onChange={() => toggleLanguageEnabled(language.code)} disabled={language.is_default} className="peer sr-only" /><span className="peer h-5 w-9 rounded-full bg-charcoal/20 after:absolute after:top-[2px] after:left-[2px] after:size-4 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-charcoal peer-checked:after:translate-x-full peer-disabled:opacity-50" /></label></td></tr>)}</tbody></table></div>
      </section>
      <div className="flex justify-end"><button type="submit" disabled={isSaving} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-charcoal px-5 py-2.5 text-xs font-semibold text-ivory hover:bg-charcoal/90 disabled:opacity-50"><Save aria-hidden="true" className="size-4" />{isSaving ? "Saving…" : "Save language settings"}</button></div>
    </form>
  );
}
