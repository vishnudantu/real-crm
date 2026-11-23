import { useQuery } from "@tanstack/react-query";
import { AlertCircle, LoaderCircle, RefreshCw, X } from "lucide-react";
import type { UserItem } from "../admin/adminModel";
import {
  formatDateTime,
  saleCardClasses,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { useModalFocus } from "../shared/useModalFocus";
import { fetchTicket, ticketKeys } from "./serviceDeskApi";
import { TicketActionsPanel, TicketCommentThread } from "./TicketActionsPanel";
import {
  isSlaBreached,
  slaCountdownLabel,
  ticketCategoryLabel,
  ticketPriorityLabel,
  ticketPriorityTone,
  ticketStatusLabel,
  ticketStatusTone,
} from "./serviceDeskModel";

interface TicketDetailDrawerProps {
  ticketId: string;
  staffUsers: readonly UserItem[];
  onClose: () => void;
}

/** Side drawer for one ticket: live detail query, thread and staff actions. */
export function TicketDetailDrawer({ ticketId, staffUsers, onClose }: TicketDetailDrawerProps) {
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const query = useQuery({
    queryKey: ticketKeys.detail(ticketId),
    queryFn: () => fetchTicket(ticketId),
  });
  const ticket = query.data;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-stretch justify-end bg-charcoal/45 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Ticket ${ticket?.ticket_number ?? ticketId}`}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden border-l border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 px-5 py-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight text-charcoal">
                {ticket ? ticket.ticket_number : "Ticket"}
              </h2>
              {ticket && (
                <>
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${ticketStatusTone(ticket.status)}`}>
                    {ticketStatusLabel(ticket.status)}
                  </span>
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${ticketPriorityTone(ticket.priority)}`}>
                    {ticketPriorityLabel(ticket.priority)}
                  </span>
                </>
              )}
            </div>
            {ticket && (
              <p className="mt-1 text-xs text-charcoal/75">{ticket.subject}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close ticket details"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {query.isLoading && (
            <div className="flex items-center justify-center gap-2 p-10 text-xs text-charcoal/65">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              <span>Loading ticket…</span>
            </div>
          )}
          {query.isError && (
            <div className="flex flex-col items-center gap-3 p-8 text-center">
              <AlertCircle aria-hidden="true" className="size-7 text-rose-500" />
              <p className="text-xs text-charcoal/65">
                {errorMessage(query.error, "The ticket could not be loaded.")}
              </p>
              <button type="button" onClick={() => void query.refetch()} className={saleSecondaryButton}>
                <RefreshCw aria-hidden="true" className="size-3.5" />
                <span>Try again</span>
              </button>
            </div>
          )}
          {ticket && (
            <div className="space-y-5">
              <section className={`${saleCardClasses} p-4`}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
                  <MetaRow label="Category" value={ticketCategoryLabel(ticket.category)} />
                  <MetaRow label="Opened" value={formatDateTime(ticket.created_at)} />
                  <MetaRow
                    label="SLA deadline"
                    value={`${formatDateTime(ticket.sla_due_at)} (${slaCountdownLabel(ticket.sla_due_at)})`}
                  />
                  <MetaRow
                    label="First response"
                    value={ticket.first_response_at ? formatDateTime(ticket.first_response_at) : "Not yet responded"}
                  />
                  {ticket.resolved_at && (
                    <MetaRow label="Resolved at" value={formatDateTime(ticket.resolved_at)} />
                  )}
                  <MetaRow
                    label="Assigned to"
                    value={
                      staffUsers.find((member) => member.id === ticket.assigned_to_id)?.full_name ??
                      (ticket.assigned_to_id ? ticket.assigned_to_id.slice(0, 8) + "…" : "Unassigned")
                    }
                  />
                  {ticket.contact_id && <MetaRow label="Contact id" value={ticket.contact_id.slice(0, 8) + "…"} />}
                  {ticket.booking_id && <MetaRow label="Booking id" value={ticket.booking_id.slice(0, 8) + "…"} />}
                </dl>
                {isSlaBreached(ticket) && (
                  <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-[11px] font-semibold text-rose-700">
                    SLA breached — this ticket is past its response deadline.
                  </p>
                )}
              </section>

              <section>
                <h3 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
                  Description
                </h3>
                <p className="mt-2 text-xs leading-6 whitespace-pre-wrap text-charcoal/80">
                  {ticket.description}
                </p>
              </section>

              {ticket.resolution_note && (
                <section className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                  <h3 className="text-[11px] font-semibold tracking-wider text-emerald-800 uppercase">
                    Resolution note
                  </h3>
                  <p className="mt-2 text-xs leading-6 whitespace-pre-wrap text-emerald-950">
                    {ticket.resolution_note}
                  </p>
                </section>
              )}

              <div className="grid gap-5 lg:grid-cols-[1fr_260px]">
                <section>
                  <h3 className="mb-3 text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
                    Thread ({ticket.comments.length})
                  </h3>
                  <TicketCommentThread ticket={ticket} />
                </section>
                <TicketActionsPanel ticket={ticket} staffUsers={staffUsers} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold tracking-wider text-charcoal/45 uppercase">
        {label}
      </dt>
      <dd className="mt-0.5 text-charcoal/80">{value}</dd>
    </div>
  );
}
