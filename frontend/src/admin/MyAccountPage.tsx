import { useState } from "react";
import type { FormEvent } from "react";
import { AlertCircle, Building2, CalendarDays, Check, CheckCircle2, Globe2, LoaderCircle, Mail, Phone, Save, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useAdminUser } from "./AdminAuthGuard";
import { updateUser } from "./api";
import { useTenant } from "../tenant/TenantProvider";
import { useFeatures } from "../features/FeaturesProvider";
import { ROLE_LABEL } from "../auth/api";
import { errorMessage } from "../shared/apiRequest";
import { AccountSecurityPanel } from "./AccountSecurityPanel";

const inputClass = "mt-1.5 w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal outline-none transition-colors placeholder:text-charcoal/35 focus:border-charcoal/45";

export function MyAccountPage() {
  const { user, refetchUser } = useAdminUser();
  const { branding } = useTenant();
  const { features } = useFeatures();
  const [fullName, setFullName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enabledFeatureCount = Object.values(features).filter(Boolean).length;
  const initials = user.full_name.split(/\s+/).map((part) => part[0]).filter(Boolean).slice(0, 2).join("").toUpperCase() || "AD";

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedName = fullName.trim();
    if (normalizedName.length < 2) {
      setError("Enter your full name using at least two characters.");
      return;
    }
    setError(null);
    setSaved(false);
    setIsSaving(true);
    try {
      await updateUser(user.id, { full_name: normalizedName, phone: phone.trim() || null });
      await refetchUser();
      setFullName(normalizedName);
      setPhone(phone.trim());
      setSaved(true);
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Your profile could not be updated."));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <header><p className="text-[0.65rem] font-semibold tracking-[0.18em] text-charcoal/50 uppercase">Personal workspace</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">My Account</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">Manage your administrator profile, account security and workspace details.</p></header>

      <section className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs">
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex min-w-0 items-center gap-4"><span className="grid size-16 shrink-0 place-items-center rounded-2xl bg-charcoal text-xl font-semibold tracking-tight text-ivory">{initials}</span><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-xl font-semibold tracking-tight">{user.full_name}</h2>{user.is_verified && <ShieldCheck aria-label="Verified account" className="size-4 text-emerald-700" />}</div><p className="mt-1 flex items-center gap-1.5 text-xs text-charcoal/55"><Building2 aria-hidden="true" className="size-3.5" />{branding.brand_name}</p></div></div>
          <div className="flex flex-wrap gap-2"><span className="rounded-full border border-charcoal/10 bg-charcoal/5 px-3 py-1.5 text-xs font-semibold">{ROLE_LABEL[user.role.name as keyof typeof ROLE_LABEL] ?? user.role.name}</span><span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">{user.is_active ? "Active account" : "Inactive account"}</span></div>
        </div>
        <div className="grid gap-px border-t border-charcoal/10 bg-charcoal/10 sm:grid-cols-2">
          <div className="flex items-center gap-3 bg-[#FAFAF7] px-5 py-4 sm:px-6"><Mail aria-hidden="true" className="size-4 shrink-0 text-charcoal/45" /><div className="min-w-0"><p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">Email address</p><p className="mt-1 truncate text-sm font-medium">{user.email}</p></div></div>
          <div className="flex items-center gap-3 bg-[#FAFAF7] px-5 py-4 sm:px-6"><CalendarDays aria-hidden="true" className="size-4 shrink-0 text-charcoal/45" /><div><p className="text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">Member since</p><p className="mt-1 text-sm font-medium">{new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(new Date(user.created_at))}</p></div></div>
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
            <div className="border-b border-charcoal/10 pb-5"><h2 className="text-base font-semibold">Profile details</h2><p className="mt-1 text-xs leading-5 text-charcoal/55">This is how your name and contact number appear to your workspace team.</p></div>
            {error && <p role="alert" className="mt-5 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-xs leading-5 text-rose-700"><AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />{error}</p>}
            {saved && <p role="status" className="mt-5 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-xs font-medium text-emerald-800"><Check aria-hidden="true" className="size-4" />Your profile has been updated.</p>}
            <form onSubmit={(event) => void saveProfile(event)} className="mt-5 space-y-4">
              <label className="block text-xs font-semibold text-charcoal/70">Full name<input required minLength={2} maxLength={255} value={fullName} onChange={(event) => { setFullName(event.target.value); setSaved(false); }} autoComplete="name" className={inputClass} /></label>
              <label className="block text-xs font-semibold text-charcoal/70">Phone number<div className="relative"><Phone aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3.5 mt-0.75 size-4 -translate-y-1/2 text-charcoal/35" /><input type="tel" maxLength={32} value={phone} onChange={(event) => { setPhone(event.target.value); setSaved(false); }} autoComplete="tel" placeholder="Add a contact number" className={`${inputClass} pl-10`} /></div></label>
              <label className="block text-xs font-semibold text-charcoal/70">Email address<input type="email" value={user.email} disabled className={`${inputClass} cursor-not-allowed bg-charcoal/5 text-charcoal/55`} /><span className="mt-1.5 block text-[0.68rem] text-charcoal/45">Contact your workspace operator to change your sign-in email.</span></label>
              <div className="flex justify-end border-t border-charcoal/10 pt-5"><button type="submit" disabled={isSaving} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-charcoal px-4 py-2 text-xs font-semibold text-ivory transition-colors hover:bg-charcoal/90 disabled:opacity-50">{isSaving ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <Save aria-hidden="true" className="size-4" />}Save profile</button></div>
            </form>
          </section>
          <AccountSecurityPanel />
        </div>

        <aside className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6 lg:sticky lg:top-28">
          <div className="flex items-center gap-2 border-b border-charcoal/10 pb-5"><SlidersHorizontal aria-hidden="true" className="size-4 text-charcoal/60" /><h2 className="text-base font-semibold">Your workspace</h2></div>
          <dl className="divide-y divide-charcoal/10">
            <div className="py-4"><dt className="flex items-center gap-2 text-[0.68rem] font-semibold tracking-wider text-charcoal/45 uppercase"><Building2 aria-hidden="true" className="size-3.5" />Organization</dt><dd className="mt-2 text-sm font-semibold">{branding.brand_name}</dd><dd className="mt-1 text-xs text-charcoal/45">@{branding.slug}</dd></div>
            <div className="py-4"><dt className="flex items-center gap-2 text-[0.68rem] font-semibold tracking-wider text-charcoal/45 uppercase"><Globe2 aria-hidden="true" className="size-3.5" />Regional settings</dt><dd className="mt-2 text-sm font-medium">{branding.timezone}</dd><dd className="mt-1 text-xs text-charcoal/55">{branding.currency} currency · {branding.date_format}</dd></div>
            <div className="py-4"><dt className="flex items-center gap-2 text-[0.68rem] font-semibold tracking-wider text-charcoal/45 uppercase"><CheckCircle2 aria-hidden="true" className="size-3.5" />Enabled features</dt><dd className="mt-2 flex items-baseline gap-2"><span className="text-2xl font-semibold tracking-tight">{enabledFeatureCount}</span><span className="text-xs text-charcoal/50">active capabilities</span></dd></div>
          </dl>
          <p className="rounded-xl bg-charcoal/5 p-3 text-[0.7rem] leading-5 text-charcoal/55">Workspace settings apply to everyone in {branding.brand_name}. Visit Settings to manage your organization’s configuration.</p>
        </aside>
      </div>
    </div>
  );
}
