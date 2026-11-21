import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ArrowRight, CheckCircle2, LoaderCircle, Lock, Mail } from "lucide-react";
import {
  ApiError,
  confirmPasswordReset,
  resetPasswordRequest,
} from "../auth/api";
import { fieldClasses } from "../auth/formStyles";
import { AuthLayout } from "../components/AuthLayout";
import { useTenant } from "../tenant/TenantProvider";

const emailSchema = z.object({
  email: z.string().trim().min(1, "Enter your email address.").email("Enter a valid email address."),
});

const passwordSchema = z.object({
  password: z.string().min(12, "Use at least 12 characters.").max(128, "Use 128 characters or fewer.")
    .regex(/[a-z]/, "Include a lowercase letter.")
    .regex(/[A-Z]/, "Include an uppercase letter.")
    .regex(/\d/, "Include a number.")
    .regex(/[^A-Za-z0-9]/, "Include a symbol."),
  confirmPassword: z.string().min(1, "Confirm your password."),
}).refine((values) => values.password === values.confirmPassword, {
  path: ["confirmPassword"],
  message: "Passwords do not match.",
});

type EmailValues = z.infer<typeof emailSchema>;
type PasswordValues = z.infer<typeof passwordSchema>;

export function ForgotPasswordPage() {
  const { branding } = useTenant();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const navigate = useNavigate();
  const [step, setStep] = useState<"request" | "sent" | "reset" | "done">(
    token ? "reset" : "request",
  );
  const [formError, setFormError] = useState<string | null>(null);
  const emailForm = useForm<EmailValues>({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: "" },
    mode: "onTouched",
  });
  const passwordForm = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { password: "", confirmPassword: "" },
    mode: "onTouched",
  });

  const errorMessage = (error: unknown): string => {
    if (error instanceof ApiError) {
      if (error.status >= 500) return `${branding.brand_name} is temporarily unavailable. Please try again.`;
      if (error.status === 422) return error.details[0]?.message || "Please check your details and try again.";
      return error.message;
    }
    return "Something went wrong. Please try again.";
  };

  const requestReset = async ({ email }: EmailValues) => {
    setFormError(null);
    try {
      await resetPasswordRequest({ email });
      setStep("sent");
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  const resetPassword = async (values: PasswordValues) => {
    setFormError(null);
    try {
      await confirmPasswordReset({
        token,
        password: values.password,
        confirmPassword: values.confirmPassword,
      });
      setStep("done");
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  const asideProps = {
    asideEyebrow: "Private access",
    asideQuote: "Secure access for every conversation.",
    asideDescription: "Your account security is protected with single-use, expiring password-reset links.",
  };
  const isSubmitting = emailForm.formState.isSubmitting || passwordForm.formState.isSubmitting;

  if (step === "sent" || step === "done") {
    const done = step === "done";
    return (
      <AuthLayout
        titleId="reset-success-heading"
        eyebrow="Password reset"
        title={done ? "Password changed" : "Check your email"}
        description={done
          ? "Your password has been changed. Sign in with your new password."
          : "If an account exists for that address, we sent a secure password-reset link. The link expires shortly and can be used once."}
        skipLabel="Skip to sign in"
        footerText={`Secure account access with ${branding.brand_name}.`}
        {...asideProps}
      >
        <div role="status" aria-live="polite" className="mb-6 flex gap-3 rounded-xl border border-forest/20 bg-forest/5 px-4 py-4 text-sm leading-6 text-forest-deep">
          {done ? <CheckCircle2 aria-hidden="true" className="mt-0.5 size-5 shrink-0" /> : <Mail aria-hidden="true" className="mt-0.5 size-5 shrink-0" />}
          <p>{done ? "All previous sessions have been signed out." : "Check your inbox and spam folder. You can close this page."}</p>
        </div>
        <button type="button" onClick={() => navigate("/login", { replace: true })} className="inline-flex min-h-[52px] items-center justify-center gap-2.5 rounded-full bg-forest px-6 text-sm font-semibold text-ivory transition-colors hover:bg-forest-deep">
          <ArrowRight className="size-4" aria-hidden="true" />
          {done ? "Sign in with new password" : "Return to sign in"}
        </button>
      </AuthLayout>
    );
  }

  const resetting = step === "reset";
  return (
    <AuthLayout
      titleId="reset-heading"
      eyebrow="Password reset"
      title={resetting ? "Choose a new password" : "Reset your password"}
      description={resetting
        ? "Use a strong password. This single-use link cannot be reused after resetting."
        : `Enter your ${branding.brand_name} account email and we will send you a secure reset link.`}
      skipLabel="Skip to password form"
      footerText="Reset links expire and can only be used once."
      {...asideProps}
    >
      {formError ? (
        <div id="reset-error" role="alert" className="mb-6 flex gap-3 rounded-xl border border-clay/25 bg-clay-soft px-4 py-3 text-sm leading-6 text-clay">
          <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <p>{formError}</p>
        </div>
      ) : null}
      <form noValidate onSubmit={resetting ? passwordForm.handleSubmit(resetPassword) : emailForm.handleSubmit(requestReset)}>
        {resetting ? (
          <>
            <label htmlFor="password" className="mb-2 block text-sm font-semibold text-charcoal">New password</label>
            <input id="password" type="password" autoComplete="new-password" required className={fieldClasses(Boolean(passwordForm.formState.errors.password))} aria-invalid={Boolean(passwordForm.formState.errors.password)} {...passwordForm.register("password")} />
            {passwordForm.formState.errors.password ? <p className="mt-2 text-sm text-clay">{passwordForm.formState.errors.password.message}</p> : null}
            <label htmlFor="confirmPassword" className="mb-2 mt-5 block text-sm font-semibold text-charcoal">Confirm new password</label>
            <input id="confirmPassword" type="password" autoComplete="new-password" required className={fieldClasses(Boolean(passwordForm.formState.errors.confirmPassword))} aria-invalid={Boolean(passwordForm.formState.errors.confirmPassword)} {...passwordForm.register("confirmPassword")} />
            {passwordForm.formState.errors.confirmPassword ? <p className="mt-2 text-sm text-clay">{passwordForm.formState.errors.confirmPassword.message}</p> : null}
          </>
        ) : (
          <>
            <label htmlFor="email" className="mb-2 block text-sm font-semibold text-charcoal">Email address</label>
            <input id="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" placeholder="name@example.com" required className={fieldClasses(Boolean(emailForm.formState.errors.email))} aria-invalid={Boolean(emailForm.formState.errors.email)} {...emailForm.register("email")} />
            {emailForm.formState.errors.email ? <p className="mt-2 text-sm text-clay">{emailForm.formState.errors.email.message}</p> : null}
          </>
        )}
        <button type="submit" disabled={isSubmitting} className="mt-6 inline-flex min-h-[52px] w-full items-center justify-center gap-2.5 rounded-full bg-forest px-6 text-sm font-semibold text-ivory transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-60">
          {isSubmitting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" /> : resetting ? <Lock className="size-4" aria-hidden="true" /> : <Mail className="size-4" aria-hidden="true" />}
          {isSubmitting ? "Please wait…" : resetting ? "Set new password" : "Send reset link"}
        </button>
        <p className="mt-6 text-sm leading-6 text-charcoal/65">
          Remember your password? <Link to="/login" className="font-semibold text-forest underline-offset-4 hover:underline">Sign in instead</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
