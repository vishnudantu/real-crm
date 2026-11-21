import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Eye, RotateCw, ScrollText, Search } from "lucide-react";
import { fetchOperatorAuditLogs } from "./api";
import { formatDateTime, humanizeIdentifier } from "./format";
import type { OperatorAuditLog } from "./operatorModel";
import {
  ErrorBlock,
  LoadingBlock,
  Modal,
  SectionHeader,
  Surface,
  inputClasses,
  secondaryButtonClasses,
} from "./ui";

export function OperatorAuditLogsPage() {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<OperatorAuditLog | null>(null);
  const logsQuery = useQuery({
    queryKey: ["operator", "audit-logs"],
    queryFn: fetchOperatorAuditLogs,
  });
  const logs = (logsQuery.data ?? []).filter((log) => {
    const haystack = `${log.action} ${log.actor_email} ${log.resource_type} ${log.resource_id ?? ""}`.toLowerCase();
    return haystack.includes(search.trim().toLowerCase());
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
          Platform accountability
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
          Operator audit log
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-charcoal/60">
          Review privileged changes to tenants, plans, deployments, and operator
          access. The API returns the latest 200 events.
        </p>
      </div>

      <Surface>
        <SectionHeader
          eyebrow="Immutable activity trail"
          title={`${logs.length} events`}
          description="Select an event to inspect its full change payload."
          action={
            <button
              type="button"
              onClick={() => void logsQuery.refetch()}
              disabled={logsQuery.isFetching}
              className={secondaryButtonClasses}
            >
              <RotateCw aria-hidden="true" className={`size-3.5 ${logsQuery.isFetching ? "animate-spin" : ""}`} />
              Refresh
            </button>
          }
        />

        <div className="border-b border-charcoal/10 px-5 py-4 sm:px-6">
          <div className="relative max-w-md">
            <Search aria-hidden="true" className="absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-charcoal/40" />
            <label htmlFor="operator-audit-search" className="sr-only">Search audit events</label>
            <input
              id="operator-audit-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search actor, action, or resource…"
              className={`${inputClasses} mt-0 pl-10`}
            />
          </div>
        </div>

        {logsQuery.isLoading ? (
          <LoadingBlock label="Loading operator audit history…" />
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
              {search ? "Try a different search term." : "Operator activity will appear here as changes are made."}
            </p>
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-charcoal/10 text-[0.62rem] font-semibold tracking-wider text-charcoal/50 uppercase">
                    <th className="px-6 py-3">Action</th>
                    <th className="px-4 py-3">Operator</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-6 py-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-charcoal/5">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-charcoal/[0.02]">
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-lg border border-forest/15 bg-forest/5 px-2.5 py-1 font-semibold text-forest-deep">
                          {humanizeIdentifier(log.action)}
                        </span>
                      </td>
                      <td className="px-4 py-4 font-medium text-charcoal/75">{log.actor_email}</td>
                      <td className="px-4 py-4">
                        <span className="block font-medium text-charcoal/75">{log.resource_type}</span>
                        <span className="mt-0.5 block max-w-40 truncate font-mono text-[0.62rem] text-charcoal/40">
                          {log.resource_id ?? "Global"}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-charcoal/55">{formatDateTime(log.created_at)}</td>
                      <td className="px-6 py-4 text-right">
                        <button
                          type="button"
                          onClick={() => setSelected(log)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-charcoal/10 px-2.5 py-1.5 font-semibold text-charcoal/65 hover:bg-charcoal/5"
                        >
                          <Eye aria-hidden="true" className="size-3.5" />
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-charcoal/10 md:hidden">
              {logs.map((log) => (
                <button
                  key={log.id}
                  type="button"
                  onClick={() => setSelected(log)}
                  className="block w-full p-5 text-left transition-colors hover:bg-charcoal/[0.02]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-charcoal">{humanizeIdentifier(log.action)}</p>
                    <Eye aria-hidden="true" className="size-4 shrink-0 text-charcoal/35" />
                  </div>
                  <p className="mt-1.5 truncate text-xs text-charcoal/60">{log.actor_email}</p>
                  <p className="mt-2 text-[0.65rem] text-charcoal/45">
                    {log.resource_type} · {formatDateTime(log.created_at)}
                  </p>
                </button>
              ))}
            </div>
          </>
        )}
      </Surface>

      {selected ? (
        <Modal
          title={humanizeIdentifier(selected.action)}
          description={`${selected.actor_email} · ${formatDateTime(selected.created_at)}`}
          onClose={() => setSelected(null)}
          widthClass="max-w-xl"
        >
          <dl className="grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-medium text-charcoal/50">Resource type</dt>
              <dd className="mt-1 font-semibold text-charcoal">{selected.resource_type}</dd>
            </div>
            <div>
              <dt className="font-medium text-charcoal/50">Resource ID</dt>
              <dd className="mt-1 font-mono text-[0.65rem] break-all text-charcoal">{selected.resource_id ?? "Global"}</dd>
            </div>
          </dl>
          <div className="mt-5">
            <h3 className="text-xs font-semibold text-charcoal/75">Change payload</h3>
            <pre className="mt-2 max-h-80 overflow-auto rounded-xl border border-charcoal/10 bg-charcoal/[0.04] p-4 font-mono text-[0.68rem] leading-5 whitespace-pre-wrap break-all text-charcoal">
              {JSON.stringify(selected.details, null, 2)}
            </pre>
          </div>
          <div className="mt-5 flex justify-end">
            <button type="button" onClick={() => setSelected(null)} className={secondaryButtonClasses}>
              Close
            </button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
