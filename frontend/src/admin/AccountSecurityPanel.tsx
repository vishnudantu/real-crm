import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, CheckCircle2, KeyRound, LoaderCircle, LogOut, ShieldCheck } from "lucide-react";
import { changePasswordRequest, revokeAllSessionsRequest } from "../auth/api";
import { clearSession } from "../auth/session";
import { errorMessage } from "../shared/apiRequest";

const inputClass = "mt-1.5 w-full rounded-xl border border-charcoal/15 bg-white px-3.5 py-2.5 text-sm text-charcoal outline-none transition-colors placeholder:text-charcoal/35 focus:border-charcoal/45";
const labelClass = "block text-xs font-semibold text-charcoal/70";

interface PasswordFields {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const EMPTY_PASSWORDS: PasswordFields = {
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
};

export function AccountSecurityPanel() {
  const navigate = useNavigate();
  const [fields, setFields] = useState<PasswordFields>(EMPTY_PASSWORDS);
  const [isChanging, setIsChanging] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateField = (key: keyof PasswordFields, value: string) => {
    setFields((current) => ({ ...current, [key]: value }));
    setError(null);
  };

  const finishSignOut = () => {
    clearSession();
    navigate("/login", { replace: true });
  };

  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (fields.newPassword !== fields.confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    if (fields.currentPassword === fields.newPassword) {
      setError("Choose a new password that differs from your current password.");
      return;
    }

    setIsChanging(true);
    try {
      await changePasswordRequest(fields);
      finishSignOut();
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Your password could not be changed."));
      setIsChanging(false);
    }
  };

  const revokeAllSessions = async () => {
    if (!window.confirm("Sign out of this account on every device? You will need to sign in again.")) return;
    setError(null);
    setIsRevoking(true);
    try {
      await revokeAllSessionsRequest();
      finishSignOut();
    } catch (reason: unknown) {
      setError(errorMessage(reason, "Your other sessions could not be revoked."));
      setIsRevoking(false);
    }
  };

  return (
    <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
      <div className="flex items-start gap-3 border-b border-charcoal/10 pb-5">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-charcoal text-ivory"><KeyRound aria-hidden="true" className="size-4" /></span>
        <div><h2 className="text-base font-semibold text-charcoal">Password & sessions</h2><p className="mt-1 text-xs leading-5 text-charcoal/55">Use a unique password and sign out unused devices to keep your workspace secure.</p></div>
      </div>

      {error && <p role="alert" className="mt-5 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-xs leading-5 text-rose-700"><AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />{error}</p>}

      <form onSubmit={(event) => void changePassword(event)} className="mt-5 space-y-4">
        <label className={labelClass}>Current password<input required type="password" autoComplete="current-password" value={fields.currentPassword} onChange={(event) => updateField("currentPassword", event.target.value)} className={inputClass} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>New password<input required minLength={12} maxLength={128} type="password" autoComplete="new-password" value={fields.newPassword} onChange={(event) => updateField("newPassword", event.target.value)} className={inputClass} /></label>
          <label className={labelClass}>Confirm new password<input required minLength={12} maxLength={128} type="password" autoComplete="new-password" value={fields.confirmPassword} onChange={(event) => updateField("confirmPassword", event.target.value)} className={inputClass} /></label>
        </div>
        <p className="text-[0.7rem] leading-5 text-charcoal/50">At least 12 characters with uppercase, lowercase, a number and a symbol. Changing your password signs out all sessions.</p>
        <button type="submit" disabled={isChanging || isRevoking} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-charcoal px-4 py-2 text-xs font-semibold text-ivory transition-colors hover:bg-charcoal/90 disabled:cursor-not-allowed disabled:opacity-50">
          {isChanging ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <CheckCircle2 aria-hidden="true" className="size-4" />}Update password
        </button>
      </form>

      <div className="mt-6 flex flex-col gap-3 border-t border-charcoal/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5"><ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-charcoal/60" /><div><h3 className="text-xs font-semibold">Other devices</h3><p className="mt-1 text-[0.7rem] leading-5 text-charcoal/50">Revoke access on every device, including this one.</p></div></div>
        <button type="button" onClick={() => void revokeAllSessions()} disabled={isChanging || isRevoking} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-50 disabled:opacity-50">{isRevoking ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <LogOut aria-hidden="true" className="size-4" />}Sign out everywhere</button>
      </div>
    </section>
  );
}
