import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTenant } from "../tenant/TenantProvider";

interface LogoProps {
  tone?: "dark" | "light";
  className?: string;
  href?: string;
}

export function Logo({ tone = "dark", className = "", href = "#top" }: LogoProps) {
  const { branding } = useTenant();
  const [logoFailed, setLogoFailed] = useState(false);
  const wordmark = tone === "dark" ? "text-charcoal" : "text-ivory";
  const mark = tone === "dark" ? "bg-charcoal text-ivory" : "bg-sand text-charcoal";
  const content = (
    <>
      {branding.logo_url && !logoFailed ? (
        <img
          src={branding.logo_url}
          alt={branding.brand_name}
          onError={() => setLogoFailed(true)}
          className="size-9 shrink-0 rounded-[10px] object-contain"
        />
      ) : (
        <span
          className={`grid size-9 shrink-0 place-items-center rounded-[10px] transition-transform duration-500 ease-out group-hover:-rotate-3 ${mark}`}
        >
          <span aria-hidden="true" className="text-base font-extrabold tracking-tight">
            {branding.brand_name.charAt(0).toUpperCase()}
          </span>
        </span>
      )}
      <span className={`text-[1.68rem] font-bold leading-none tracking-[-0.045em] ${wordmark}`}>
        {branding.brand_name}
      </span>
    </>
  );

  useEffect(() => setLogoFailed(false), [branding.logo_url]);

  if (/^(#|https?:|mailto:|tel:)/.test(href)) {
    return (
      <a
        href={href}
        aria-label={`${branding.brand_name} home`}
        className={`group inline-flex items-center gap-2.5 ${className}`}
      >
        {content}
      </a>
    );
  }

  return (
    <Link
      to={href}
      aria-label={`${branding.brand_name} home`}
      className={`group inline-flex items-center gap-2.5 ${className}`}
    >
      {content}
    </Link>
  );
}
