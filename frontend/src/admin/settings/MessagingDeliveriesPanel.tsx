import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Inbox,
  LoaderCircle,
  RotateCw,
  X,
} from "lucide-react";
import { useModalFocus } from "../../shared/useModalFocus";
import { fetchMessageDeliveries } from "../messagingApi";
import type {
  DeliveryStatus,
  MessageChannel,
  MessageDeliveryItem,
} from "../messagingModel";
import {
  CHANNELS,
  DELIVERY_STATUSES,
  channelBadgeClasses,
  channelLabel,
  deliveryStatusClasses,
  formatDeliveryDate,
  messagingSecondaryButton,
} from "./messagingUi";

interface DeliveryFilters {
  page: number;
  status: DeliveryStatus | "ALL";
  channel: MessageChannel | "ALL";
}

const DEFAULT_FILTERS: DeliveryFilters = { page: 1, status: "ALL", channel: "ALL" };

export function MessagingDeliveriesPanel() {
  const [filters, setFilters] = useState<DeliveryFilters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<MessageDeliveryItem | null>(null);
  const deliveriesQuery = useQuery({
    queryKey: [
      "messaging",
      "deliveries",
      filters.page,
      filters.status,
      filters.channel,
    ],
    queryFn: () =>
      fetchMessageDeliveries({
        page: filters.page,
        pageSize: 15,
        status: filters.status,
        channel: filters.channel,
      }),
    placeholderData: keepPreviousData,
  });
  const data = deliveriesQuery.data;
  const items = data?.items ?? [];
  const pages = data?.pages ?? 0;

  const changeFilters = (next: Partial<Omit<DeliveryFilters, "page">>) => {
    setFilters((current) => ({ ...current, ...next, page: 1 }));
  };

  return (
    <section aria-labelledby="messaging-deliveries-heading">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 id="messaging-deliveries-heading" className="text-sm font-semibold text-charcoal">
            Delivery log
          </h3>
          <p className="mt-1 text-xs leading-5 text-charcoal/55">
            Track queued, sent, and failed messages across every provider.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="delivery-status-filter" className="sr-only">Filter by delivery status</label>
          <select
            id="delivery-status-filter"
            value={filters.status}
            onChange={(event) =>
              changeFilters({ status: event.target.value as DeliveryStatus | "ALL" })
            }
            className="min-h-9 rounded-xl border border-charcoal/15 bg-white px-3 text-[11px] font-semibold text-charcoal/70"
          >
            <option value="ALL">All statuses</option>
            {DELIVERY_STATUSES.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
          <label htmlFor="delivery-channel-filter" className="sr-only">Filter by channel</label>
          <select
            id="delivery-channel-filter"
            value={filters.channel}
            onChange={(event) =>
              changeFilters({ channel: event.target.value as MessageChannel | "ALL" })
            }
            className="min-h-9 rounded-xl border border-charcoal/15 bg-white px-3 text-[11px] font-semibold text-charcoal/70"
          >
            <option value="ALL">All channels</option>
            {CHANNELS.map((channel) => (
              <option key={channel.value} value={channel.value}>{channel.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void deliveriesQuery.refetch()}
            disabled={deliveriesQuery.isFetching}
            aria-label="Refresh delivery log"
            className="grid size-9 place-items-center rounded-xl border border-charcoal/15 bg-white text-charcoal/60 hover:bg-charcoal/5 disabled:opacity-50"
          >
            <RotateCw aria-hidden="true" className={`size-3.5 ${deliveriesQuery.isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-2xl border border-charcoal/10 bg-white">
        {deliveriesQuery.isLoading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-xs text-charcoal/50">
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            Loading delivery history…
          </div>
        ) : deliveriesQuery.isError ? (
          <div role="alert" className="p-5 text-center">
            <p className="text-xs text-clay">
              {deliveriesQuery.error instanceof Error
                ? deliveriesQuery.error.message
                : "Failed to load delivery history."}
            </p>
            <button
              type="button"
              onClick={() => void deliveriesQuery.refetch()}
              className={`${messagingSecondaryButton} mt-3`}
            >
              Try again
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Inbox aria-hidden="true" className="mx-auto size-5 text-charcoal/35" />
            <p className="mt-2 text-xs font-semibold text-charcoal">No deliveries found</p>
            <p className="mt-1 text-[11px] text-charcoal/50">
              Send a test message or adjust the filters to see delivery activity.
            </p>
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="w-full min-w-[850px] text-left text-[11px]">
                <thead>
                  <tr className="border-b border-charcoal/10 text-[10px] font-semibold tracking-wider text-charcoal/50 uppercase">
                    <th className="px-5 py-3">Status</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Channel</th>
                    <th className="px-4 py-3">Event</th>
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Attempts</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-5 py-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-charcoal/5">
                  {items.map((delivery) => (
                    <tr key={delivery.id} className="hover:bg-charcoal/[0.02]">
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex rounded-md border px-2 py-1 text-[10px] font-semibold ${deliveryStatusClasses(delivery.status)}`}>
                          {delivery.status}
                        </span>
                      </td>
                      <td className="max-w-44 truncate px-4 py-3.5 font-semibold text-charcoal" title={delivery.to_address}>
                        {delivery.to_address}
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${channelBadgeClasses(delivery.channel)}`}>
                          {channelLabel(delivery.channel)}
                        </span>
                      </td>
                      <td className="max-w-40 truncate px-4 py-3.5 font-mono text-[10px] text-charcoal/65" title={delivery.event}>
                        {delivery.event}
                      </td>
                      <td className="px-4 py-3.5 text-charcoal/60">{delivery.provider}</td>
                      <td className="px-4 py-3.5 text-charcoal/60">{delivery.attempts}</td>
                      <td className="px-4 py-3.5 whitespace-nowrap text-charcoal/55">{formatDeliveryDate(delivery.created_at)}</td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          type="button"
                          onClick={() => setSelected(delivery)}
                          aria-label={`Inspect delivery to ${delivery.to_address}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-charcoal/10 px-2 py-1 font-semibold text-charcoal/60 hover:bg-charcoal/5"
                        >
                          <Eye aria-hidden="true" className="size-3" />
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-charcoal/10 lg:hidden">
              {items.map((delivery) => (
                <button
                  key={delivery.id}
                  type="button"
                  onClick={() => setSelected(delivery)}
                  className="block w-full p-4 text-left hover:bg-charcoal/[0.02]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-charcoal">{delivery.to_address}</p>
                      <p className="mt-1 font-mono text-[10px] text-charcoal/50">{delivery.event}</p>
                    </div>
                    <span className={`shrink-0 rounded-md border px-2 py-1 text-[10px] font-semibold ${deliveryStatusClasses(delivery.status)}`}>
                      {delivery.status}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-charcoal/55">
                    <span>{channelLabel(delivery.channel)}</span>
                    <span>{delivery.provider}</span>
                    <span>{delivery.attempts} attempts</span>
                    <span>{formatDeliveryDate(delivery.created_at)}</span>
                  </div>
                  {delivery.error ? (
                    <p className="mt-2 line-clamp-2 text-[10px] leading-4 text-clay">{delivery.error}</p>
                  ) : null}
                </button>
              ))}
            </div>

            <div className="flex flex-col gap-3 border-t border-charcoal/10 px-4 py-3 text-[11px] text-charcoal/55 sm:flex-row sm:items-center sm:justify-between sm:px-5">
              <span>
                {data?.total.toLocaleString("en-IN") ?? 0} deliveries · Page {filters.page} of {Math.max(pages, 1)}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}
                  disabled={filters.page <= 1 || deliveriesQuery.isFetching}
                  aria-label="Previous delivery page"
                  className="grid size-8 place-items-center rounded-lg border border-charcoal/15 disabled:opacity-35"
                >
                  <ChevronLeft aria-hidden="true" className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}
                  disabled={pages === 0 || filters.page >= pages || deliveriesQuery.isFetching}
                  aria-label="Next delivery page"
                  className="grid size-8 place-items-center rounded-lg border border-charcoal/15 disabled:opacity-35"
                >
                  <ChevronRight aria-hidden="true" className="size-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {selected ? (
        <DeliveryDetailsModal delivery={selected} onClose={() => setSelected(null)} />
      ) : null}
    </section>
  );
}

interface DeliveryDetailsModalProps {
  delivery: MessageDeliveryItem;
  onClose: () => void;
}

function DeliveryDetailsModal({ delivery, onClose }: DeliveryDetailsModalProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/45 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Delivery details"
        className="max-h-[90svh] w-full max-w-xl overflow-y-auto rounded-2xl border border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-charcoal">Delivery details</h2>
              <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${deliveryStatusClasses(delivery.status)}`}>
                {delivery.status}
              </span>
            </div>
            <p className="mt-1 font-mono text-[10px] text-charcoal/45">{delivery.id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close delivery details"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div className="p-5">
          <dl className="grid gap-x-4 gap-y-3 text-xs sm:grid-cols-2">
            {[
              ["Recipient", delivery.to_address],
              ["Channel", channelLabel(delivery.channel)],
              ["Provider", delivery.provider],
              ["Event", delivery.event],
              ["Attempts", String(delivery.attempts)],
              ["Created", formatDeliveryDate(delivery.created_at)],
              ["Sent", formatDeliveryDate(delivery.sent_at)],
              ["Next attempt", formatDeliveryDate(delivery.next_attempt_at)],
              ["Provider message ID", delivery.provider_msg_id ?? "—"],
              ["Entity", delivery.entity_type ? `${delivery.entity_type} · ${delivery.entity_id ?? "—"}` : "—"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-[10px] font-semibold tracking-wider text-charcoal/45 uppercase">{label}</dt>
                <dd className="mt-1 break-all text-charcoal/80">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-5">
            <h3 className="text-[10px] font-semibold tracking-wider text-charcoal/45 uppercase">Message body</h3>
            <p className="mt-2 max-h-48 overflow-y-auto rounded-xl bg-charcoal/[0.04] p-3.5 text-xs leading-5 whitespace-pre-wrap text-charcoal/80">
              {delivery.body}
            </p>
          </div>

          {delivery.error ? (
            <div className="mt-4 rounded-xl border border-clay/25 bg-clay-soft p-3.5">
              <h3 className="text-[10px] font-semibold tracking-wider text-clay uppercase">Provider error</h3>
              <p className="mt-1.5 text-xs leading-5 whitespace-pre-wrap text-clay">{delivery.error}</p>
            </div>
          ) : null}

          <div className="mt-5 flex justify-end">
            <button type="button" onClick={onClose} className={messagingSecondaryButton}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}
