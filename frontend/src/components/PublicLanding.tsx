import { Link } from "react-router-dom";
import { ArrowUpRight, Building2, CalendarCheck, MessageSquareText, ShieldCheck } from "lucide-react";
import { useTenant } from "../tenant/TenantProvider";
import { isTenantBranded } from "../tenant/branding";

const benefits = [
  { icon: MessageSquareText, title: "A considered reply", text: "Respond with the approved facts for each project." },
  { icon: CalendarCheck, title: "Genuine visit slots", text: "Offer visits only when your team is available." },
  { icon: ShieldCheck, title: "Human handover", text: "Give your sales team the full conversation and buyer context." },
];

export function PublicLanding() {
  const { branding } = useTenant();
  const tenantBranded = isTenantBranded(branding);

  return (
    <div className="min-h-svh bg-ivory text-charcoal">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-charcoal focus:px-4 focus:py-3 focus:text-white">
        Skip to content
      </a>
      <header className="shell flex min-h-20 items-center justify-between gap-4">
        <Link to="/" className="inline-flex items-center gap-2.5 text-xl font-extrabold tracking-tight">
          {branding.logo_url ? <img src={branding.logo_url} alt={branding.brand_name} className="size-9 object-contain" /> : <Building2 aria-hidden="true" className="size-7 text-forest" />}
          {branding.brand_name}
        </Link>
        <Link to="/login" className="rounded-full border border-charcoal/20 px-5 py-2.5 text-sm font-semibold hover:bg-charcoal hover:text-ivory">
          Sign in
        </Link>
      </header>
      <main id="main" className="shell pb-20 pt-14 sm:pt-20">
        <p className="eyebrow">The residential enquiry desk</p>
        <h1 className="mt-5 max-w-[15ch] text-[clamp(2.5rem,6vw,5rem)] font-bold leading-[1.02] tracking-[-0.045em]">
          Every enquiry deserves a considered next step.
        </h1>
        <p className="mt-6 max-w-[52ch] text-base leading-7 text-charcoal/70">
          {branding.brand_name} helps your team respond with approved project facts, arrange real site visits, and hand serious buyers to a named executive with context.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/register" className="inline-flex min-h-12 items-center gap-2 rounded-full brand-button px-6 text-sm font-semibold">
            Create buyer account <ArrowUpRight aria-hidden="true" className="size-4" />
          </Link>
          <a href="#capabilities" className="inline-flex min-h-12 items-center rounded-full border border-charcoal/20 px-6 text-sm font-semibold">
            Explore the enquiry desk
          </a>
        </div>
        <ul id="capabilities" className="mt-16 grid gap-px overflow-hidden rounded-2xl border border-charcoal/10 bg-charcoal/10 md:grid-cols-3">
          {benefits.map(({ icon: Icon, title, text }) => (
            <li key={title} className="bg-ivory p-6">
              <Icon aria-hidden="true" className="size-6 text-forest" />
              <h2 className="mt-4 text-lg font-bold tracking-tight">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-charcoal/65">{text}</p>
            </li>
          ))}
        </ul>
      </main>
      <footer className="shell border-t border-charcoal/10 py-6 text-xs text-charcoal/60">
        <p>&copy; {new Date().getFullYear()} {branding.brand_name}. Residential enquiry management.</p>
        {tenantBranded && (
          <p className="mt-2 text-charcoal/45">Powered by PropFlow</p>
        )}
      </footer>
    </div>
  );
}
