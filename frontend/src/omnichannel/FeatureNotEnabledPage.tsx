import { Lock } from "lucide-react";
import { Link } from "react-router-dom";

export function FeatureNotEnabledPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-charcoal/5 text-charcoal/50">
        <Lock aria-hidden="true" className="size-7" />
      </span>
      <div>
        <h1 className="text-lg font-semibold text-charcoal">
          This capability is not enabled
        </h1>
        <p className="mt-1 max-w-md text-sm text-charcoal/60">
          Your organization does not have access to this module yet. Contact your
          PropFlow operator to enable it for your tenant.
        </p>
      </div>
      <Link
        to="/admin"
        className="rounded-lg bg-charcoal px-4 py-2 text-xs font-semibold text-ivory hover:opacity-90"
      >
        Back to overview
      </Link>
    </div>
  );
}
