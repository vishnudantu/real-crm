import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { ApiError } from "../auth/api";
import { fetchOperatorProfile, loginOperator } from "./api";
import {
  clearOperatorSession,
  getOperatorSession,
  saveOperatorSession,
} from "./session";
import { inputClasses, labelClasses } from "./ui";
import { Logo } from "../components/Logo";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your operator email.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type LoginValues = z.infer<typeof loginSchema>;

export function OperatorLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    document.title = "Operator sign in — PropFlow";
  }, []);

  useEffect(() => {
    if (location.state || !getOperatorSession()) return;
    let active = true;

    async function resumeSession() {
      try {
        await fetchOperatorProfile();
        if (active) navigate("/operator", { replace: true });
      } catch {
        clearOperatorSession();
      }
    }

    void resumeSession();
    return () => {
      active = false;
    };
  }, [location.state, navigate]);

  const onSubmit = async (values: LoginValues) => {
    setFormError(null);
    try {
      const token = await loginOperator(values.email, values.password);
      saveOperatorSession(token.access_token, token.expires_in);
      const from = (location.state as {
        from?: { pathname?: string; search?: string; hash?: string };
      } | null)?.from;
      const destination = from?.pathname
        ? `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
        : "/operator";
      navigate(destination === "/operator/login" ? "/operator" : destination, {
        replace: true,
      });
    } catch (error: unknown) {
      setFormError(
        error instanceof ApiError
          ? error.message
          : "Unable to sign in. Please try again.",
      );
    }
  };

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-charcoal px-4 py-10 sm:px-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 -right-40 size-[28rem] rounded-full bg-forest/25 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-48 -left-32 size-[26rem] rounded-full bg-sand/15 blur-3xl"
      />

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex items-center justify-between">
          <Logo href="/operator/login" tone="light" />
          <span className="rounded-full border border-ivory/20 px-3 py-1 text-[0.62rem] font-semibold tracking-[0.18em] text-ivory/70 uppercase">
            Control plane
          </span>
        </div>

        <div className="rounded-3xl border border-ivory/10 bg-ivory p-6 shadow-2xl sm:p-8">
          <span className="grid size-11 place-items-center rounded-2xl bg-forest/10 text-forest">
            <ShieldCheck aria-hidden="true" className="size-5" />
          </span>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight text-charcoal">
            Operator access
          </h1>
          <p className="mt-2 text-sm leading-6 text-charcoal/65">
            Provision tenants, manage subscription plans, and oversee PropFlow
            deployments. This account is separate from tenant admin accounts.
          </p>

          {formError ? (
            <div
              role="alert"
              className="mt-5 flex items-start gap-2.5 rounded-xl border border-clay/25 bg-clay-soft px-3.5 py-3 text-sm text-clay"
            >
              <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <p>{formError}</p>
            </div>
          ) : null}

          <form noValidate onSubmit={handleSubmit(onSubmit)} className="mt-6">
            <div>
              <label htmlFor="operator-email" className={labelClasses}>
                Work email
              </label>
              <input
                id="operator-email"
                type="email"
                autoComplete="username"
                autoCapitalize="none"
                placeholder="operator@propflow.example"
                aria-invalid={Boolean(errors.email)}
                className={inputClasses}
                {...register("email")}
              />
              {errors.email ? (
                <p className="mt-1.5 text-xs text-clay">{errors.email.message}</p>
              ) : null}
            </div>

            <div className="mt-4">
              <label htmlFor="operator-password" className={labelClasses}>
                Password
              </label>
              <div className="relative">
                <input
                  id="operator-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  aria-invalid={Boolean(errors.password)}
                  className={`${inputClasses} pr-12`}
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute top-1/2 right-3 -translate-y-1/2 rounded-md p-1.5 text-charcoal/50 transition-colors hover:text-charcoal"
                >
                  {showPassword ? (
                    <EyeOff aria-hidden="true" className="size-4" />
                  ) : (
                    <Eye aria-hidden="true" className="size-4" />
                  )}
                </button>
              </div>
              {errors.password ? (
                <p className="mt-1.5 text-xs text-clay">{errors.password.message}</p>
              ) : null}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-forest px-5 text-sm font-semibold text-white transition-colors hover:bg-forest-deep disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                  Verifying access…
                </>
              ) : (
                <>
                  Sign in to control plane
                  <ArrowRight aria-hidden="true" className="size-4" />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 flex items-center justify-center gap-2 text-center text-xs leading-5 text-ivory/60">
          <LockKeyhole aria-hidden="true" className="size-3.5" />
          Access is limited to authorized PropFlow operators and every change is
          audited.
        </p>
      </div>
    </div>
  );
}
