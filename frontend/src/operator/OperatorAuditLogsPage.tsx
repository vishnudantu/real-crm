import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ChevronDown,
  ChevronRight,
  Eye,
  ExternalLink,
  RotateCw,
  ScrollText,
} from "lucide-react";
import { fetchOperatorAuditLogs } from "./api";
import { formatDateTime } from "./format";
import { useOperator } from "./OperatorAuthGuard";
import {
  AUDIT_ACTION_OPTIONS,
  AUDIT_RESOURCE_TYPE_OPTIONS,
  humanizeAction,
  humanizeIdentifier,
  isUuidLike,
  summarizeAuditDetails,
} from "./operatorModel";
import type { OperatorAuditLog } from "./operatorModel";
import {
  ErrorBlock,
  LoadingBlock,
  SectionHeader,
  Surface,
  inputClasses,
  labelClasses,
  secondaryButtonClasses,
} from "./ui";

const LIMIT_STEPS = [100, 200, 500] as const;

const ACTION_FALLBACKS = [
  "TENANT_PROVISIONED",
  "TENANT_STATUS_CHANGED",
  "TENANT_CONFIG_UPDATED",
  "FEATURE_ENABLED",
  "FEATURE_DISABLED",
  "FEATURE_RESET",
  "PLAN_CREATED",
  "PLAN_UPDATED",
  "OPERATOR_CREATED",
  "OPERATOR_UPDATED",
  "DEPLOYMENT_REQUESTED",
  "IMPERSONATION_STARTED",
];

function tenantLinkFor(log: OperatorAuditLog): string | null {
  if (log.resource_type !== "TENANT") return null;
  if (!isUuidLike(log.resource_id)) return null;
  return `/operator/tenants/${log.resource_id}`;
}

interface AuditRowProps {
  log: OperatorAuditLog;
  expanded: boolean;
  onToggle: () => void;
}

function AuditRow({ log, expanded, onToggle }: AuditRowProps) {
  const link = tenantLinkFor(log);
  const summary = summarizeAuditDetails(log.details);

  return (
    <>
      <tr className="hover:bg-charcoal/[0.02]">
        <td className="px-6 py-4">
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            className="inline-flex items-center gap-2 rounded-lg border border-forest/15 bg-forest/5 px-2.5 py-1 font-semibold text-forest-deep transition-colors hover:bg-forest/10"
          >
            {humanizeAction(log.action)}
            <ChevronDown
              aria-hidden="true"
              className={`size-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        </td>
        <td className="px-4 py-4 font-medium text-charcoal/75">{log.actor_email}</td>
        <td className="px-4 py-4">
          <span className="block font-medium text-charcoal/75">{humanizeIdentifier(log.resource_type)}</span>
          <span className="mt-0.5 block max-w-40 truncate font-mono text-[0.62rem] text-charcoal/40">
            {log.resource_id ?? "Global"}
          </span>
        </td>
        <td className="max-w-48 px-4 py-4 text-charcoal/60">
          <span className="block truncate">{summary}</span>
        </td>
        <td className="px-4 py-4 whitespace-nowrap text-charcoal/55">{formatDateTime(log.created_at)}</td>
        <td className="px-6 py-4 text-right">
          <div className="inline-flex items-center gap-1.5">
            {link ? (
              <Link
                to={link}
                className="inline-flex items-center gap-1.5 rounded-lg border border-forest/20 bg-forest/5 px-2.5 py-1.5 font-semibold text-forest-deep transition-colors hover:bg-forest/10"
              >
                <Building2 aria-hidden="true" className="size-3.5" />
                Tenant 360
              </Link>
            ) : null}
            <button
              type="button"
              onClick={onToggle}
              className="inline-flex items-center gap-1.5 rounded-lg border border-charcoal/10 px-2.5 py-1.5 font-semibold text-charcoal/65 hover:bg-charcoal/5"
            >
              <Eye aria-hidden="true" className="size-3.5" />
              JSON
            </button>
          </div>
        </td>
      </tr>
      {expanded ? (
        <tr className="bg-[#FAFAF7]">
          <td colSpan={6} className="px-6 py-4">
            <pre className="max-h-72 overflow-auto rounded-xl border border-charcoal/10 bg-charcoal/[0.04] p-4 font-mono text-[0.66rem] leading-5 whitespace-pre-wrap break-all text-charcoal">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function AuditCardRow({ log }: { log: OperatorAuditLog }) {
  const [expanded, setExpanded] = useState(false);
  const link = tenantLinkFor(log);

  return (
    <li className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="inline-flex rounded-lg border border-forest/15 bg-forest/5 px-2.5 py-1 text-[0.65rem] font-semibold text-forest-deep">
            {humanizeAction(log.action)}
          </span>
          <p className="mt-1.5 truncate text-xs text-charcoal/70">{log.actor_email}</p>
          <p className="mt-1 text-[0.68rem] text-charcoal/55">{summarizeAuditDetails(log.details)}</p>
          <p className="mt-1 text-[0.62rem] text-charcoal/45">
            {humanizeIdentifier(log.resource_type)} · {formatDateTime(log.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {link ? (
            <Link
              to={link}
              className="inline-flex items-center gap-1 text-[0.65rem] font-semibold text-forest"
            >
              Tenant 360
              <ExternalLink aria-hidden="true" className="size-3" />
            </Link>
          ) : null}
          <button
            type="button"
            onClick={() => setExpanded((previous) => !previous)}
            aria-expanded={expanded}
            className="inline-flex items-center gap-1 text-[0.65rem] font-semibold text-charcoal/55"
          >
            {expanded ? "Hide JSON" : "Show JSON"}
            {expanded ? (
              <ChevronDown aria-hidden="true" className="size-3" />
            ) : (
              <ChevronRight aria-hidden="true" className="size-3" />
            )}
          </button>
        </div>
      </div>
      {expanded ? (
        <pre className="mt-3 max-h-72 overflow-auto rounded-xl border border-charcoal/10 bg-charcoal/[0.04] p-4 font-mono text-[0.64rem] leading-5 whitespace-pre-wrap break-all text-charcoal">
          {JSON.stringify(log.details, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}

export function OperatorAuditLogsPage() {
  const { can } = useOperator();
  const [searchParams, setSearchParams] = useSearchParams();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [limitIndex, setLimitIndex] = useState(0);

  const action = searchParams.get("action") ?? "";
  const resourceType = searchParams.get("resource_type") ?? "";
  const actorEmail = searchParams.get("actor_email") ?? "";
  const tenantSlug = searchParams.get("tenant_slug") ?? "";
  const limit = LIMIT_STEPS[Math.min(limitIndex, LIMIT_STEPS.length - 1)];

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const logsQuery = useQuery({
    queryKey: ["operator", "audit-logs", { action, resourceType, actorEmail, tenantSlug, limit }],
    queryFn: () =>
      fetchOperatorAuditLogs({
        ...(action ? { action } : {}),
        ...(resourceType ? { resource_type: resourceType } : {}),
        ...(actorEmail ? { actor_email: actorEmail } : {}),
        ...(tenantSlug ? { tenant_slug: tenantSlug } : {}),
        limit,
      }),
  });

  const actionOptions = useMemo(() => {
    const seen = new Set(ACTION_FALLBACKS);
    for (const option of AUDIT_ACTION_OPTIONS) seen.add(option);
    for (const log of logsQuery.data ?? []) seen.add(log.action);
    return Array.from(seen).sort();
  }, [logsQuery.data]);

  const resourceOptions = useMemo(() => {
    const seen = new Set(AUDIT_RESOURCE_TYPE_OPTIONS);
    for (const log of logsQuery.data ?? []) seen.add(log.resource_type);
    return Array.from(seen).sort();
  }, [logsQuery.data]);

  const logs = logsQuery.data ?? [];
  const hasFilters = Boolean(action || resourceType || actorEmail || tenantSlug);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
          Trust &amp; Access
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
          Audit explorer
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
          Filter the privileged control-plane trail by action, resource type,
          actor, or tenant slug. Server-side filtering via GET /operator/audit-logs.
        </p>
      </div>

      <Surface>
        <SectionHeader
          eyebrow="Immutable activity trail"
          title={`${logs.length} events${hasFilters ? " (filtered)" : ""}`}
          description="Expand a row to inspect the full change payload as pretty-printed JSON."
          action={
            <div className="flex items-center gap-2">
              {hasFilters ? (
                <button
                  type="button"
                  onClick={() => setSearchParams({}, { replace: true })}
                  className="inline-flex min-h-10 items-center rounded-xl border border-charcoal/15 bg-white px-3.5 text-xs font-semibold text-clay"
                >
                  Clear filters
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => void logsQuery.refetch()}
                disabled={logsQuery.isFetching}
                className={secondaryButtonClasses}
              >
                <RotateCw aria-hidden="true" className={`size-3.5 ${logsQuery.isFetching ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          }
        />

        <div className="grid gap-3 border-b border-charcoal/10 px-5 py-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
          <div>
            <label htmlFor="audit-action" className={labelClasses}>Action</label>
            <select
              id="audit-action"
              value={action}
              onChange={(event) => setParam("action", event.target.value)}
              className={inputClasses}
            >
              <option value="">All actions</option>
              {actionOptions.map((option) => (
                <option key={option} value={option}>{humanizeAction(option)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="audit-resource" className={labelClasses}>Resource type</label>
            <select
              id="audit-resource"
              value={resourceType}
              onChange={(event) => setParam("resource_type", event.target.value)}
              className={inputClasses}
            >
              <option value="">All resources</option>
              {resourceOptions.map((option) => (
                <option key={option} value={option}>{humanizeIdentifier(option)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="audit-actor" className={labelClasses}>Actor email</label>
            <input
              id="audit-actor"
              type="email"
              value={actorEmail}
              placeholder="ops@propflow.example"
              onChange={(event) => setParam("actor_email", event.target.value.trim())}
              className={inputClasses}
            />
          </div>
          <div>
            <label htmlFor="audit-slug" className={labelClasses}>Tenant slug</label>
            <input
              id="audit-slug"
              value={tenantSlug}
              placeholder="acme-realty"
              onChange={(event) => setParam("tenant_slug", event.target.value.trim())}
              className={inputClasses}
            />
          </div>
        </div>

        {logsQuery.isLoading ? (
          <LoadingBlock label="Loading audit history…" />
        ) : logsQuery.isError ? (
          <ErrorBlock
            message={
              logsQuery.error instanceof Error
                ? logsQuery.error.message
                : "Failed to load audit history."
            }
            onRetry={() => void logsQuery.refetch()}
          />
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-12 text-center">
            <ScrollText aria-hidden="true" className="size-6 text-charcoal/35" />
            <p className="mt-3 text-sm font-semibold text-charcoal">No matching events</p>
            <p className="mt-1 text-xs text-charcoal/55">
              {hasFilters
                ? "No audit entries match these filters. Clear them or widen the window."
                : "Operator activity will appear here as changes are made."}
            </p>
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-charcoal/10 text-[0.62rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                    <th className="px-6 py-3">Action</th>
                    <th className="px-4 py-3">Actor</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Summary</th>
                    <th className="px-4 py-3">When</th>
                    <th className="px-6 py-3 text-right">Links</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-charcoal/5">
                  {logs.map((log) => (
                    <AuditRow
                      key={log.id}
                      log={log}
                      expanded={expandedId === log.id}
                      onToggle={() =>
                        setExpandedId((previous) => (previous === log.id ? null : log.id))
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-charcoal/10 lg:hidden">
              {logs.map((log) => (
                <AuditCardRow key={log.id} log={log} />
              ))}
            </ul>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-charcoal/10 px-5 py-4 sm:px-6">
              <p className="text-[0.65rem] text-charcoal/50">
                Showing {logs.length} of up to {limit} requested · newest first
              </p>
              {limit < 500 && logs.length >= limit ? (
                <button
                  type="button"
                  onClick={() => setLimitIndex((index) => Math.min(index + 1, LIMIT_STEPS.length - 1))}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-charcoal/15 bg-white px-3 py-2 text-xs font-semibold text-forest transition-colors hover:bg-charcoal/5"
                >
                  Load more (up to {LIMIT_STEPS[Math.min(limitIndex + 1, LIMIT_STEPS.length - 1)]})
                </button>
              ) : null}
            </div>
          </>
        )}
      </Surface>

      {!can("tenants.read") ? (
        <p className="text-[0.68rem] text-charcoal/50">
          Tenant 360 deep links require tenants.read; they are hidden for your role.
        </p>
      ) : null}
    </div>
  );
}
