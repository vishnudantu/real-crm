import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  Inbox,
  LoaderCircle,
  Plus,
  RefreshCw,
} from "lucide-react";
import { fetchUsers } from "../admin/api";
import {
  formatDateTime,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import { ApprovalPagination } from "../approvals/ApprovalsUi";
import { CreateTicketModal } from "./CreateTicketModal";
import { TicketDetailDrawer } from "./TicketDetailDrawer";
import { fetchTickets, ticketKeys } from "./serviceDeskApi";
import type { TicketItem, TicketPriority, TicketStatus } from "./serviceDeskModel";
import {
  TICKET_PRIORITIES,
  TICKET_STATUSES,
  isSlaBreached,
  slaCountdownLabel,
  ticketCategoryLabel,
  ticketPriorityLabel,
  ticketPriorityTone,
  ticketStatusLabel,
  ticketStatusTone,
  totalPages,
} from "./serviceDeskModel";

const PAGE_SIZE = 25;

/** /admin/service-desk — support queue with SLA filters, creation and thread actions. */
export function ServiceDeskPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<TicketStatus | "ALL">("ALL");
  const [priority, setPriority] = useState<TicketPriority | "ALL">("ALL");
  const [breachOnly, setBreachOnly] = useState(false);
  const [assignedToId, setAssignedToId] = useState<string | "ALL">("ALL");
  const [openTicketId, setOpenTicketId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ticketKeys.list(page, PAGE_SIZE, status, priority, breachOnly, assignedToId),
    queryFn: () => fetchTickets({ page, pageSize: PAGE_SIZE, status, priority, breachOnly, assignedToId }),
  });
  const breachCountQuery = useQuery({
    queryKey: [...ticketKeys.all, "breach-count"],
    queryFn: () =>
      fetchTickets({ page: 1, pageSize: 1, status: "ALL", priority: "ALL", breachOnly: true, assignedToId: "ALL" }),
    staleTime: 30_000,
  });
  const staffQuery = useQuery({
    queryKey: ["admin", "users", "active-staff"],
    queryFn: () => fetchUsers({ page: 1, pageSize: 100, status: "ACTIVE" }),
    staleTime: 120_000,
  });

  const tickets = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const pageCount = totalPages(total, PAGE_SIZE);
  const staffUsers = (staffQuery.data?.items ?? []).filter(
    (member) => member.role.name === "ADMIN" || member.role.name === "SALES_EXECUTIVE",
  );

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice((prev) => (prev === message ? null : prev)), 4500);
  };

  const filtersActive = status !== "ALL" || priority !== "ALL" || breachOnly || assignedToId !== "ALL";
  const resetFilters = () => {
    setStatus("ALL");
    setPriority("ALL");
    setBreachOnly(false);
    setAssignedToId("ALL");
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-sans text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
            Service desk
          </h1>
          <p className="mt-1 text-sm text-charcoal/65">
            Support tickets with SLA tracking
            {typeof breachCountQuery.data?.total === "number" && breachCountQuery.data.total > 0 && (
              <>
                {" · "}
                <span className="inline-flex items-center gap-1 font-semibold text-rose-700">
                  <AlertTriangle aria-hidden="true" className="size-3.5" />
                  {breachCountQuery.data.total} past SLA
                </span>
              </>
            )}
            .
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className={salePrimaryButton}
          aria-label="Create a support ticket"
        >
          <Plus aria-hidden="true" className="size-4" />
          <span>New ticket</span>
        </button>
      </div>

      <ServiceDeskFilters
        status={status}
        onStatusChange={(value) => { setStatus(value); setPage(1); }}
        priority={priority}
        onPriorityChange={(value) => { setPriority(value); setPage(1); }}
        breachOnly={breachOnly}
        onBreachOnlyChange={(value) => { setBreachOnly(value); setPage(1); }}
        assignedToId={assignedToId}
        onAssignedToChange={(value) => { setAssignedToId(value); setPage(1); }}
        staffUsers={staffUsers}
      />

      {notice && (
        <div
          role="status"
          className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 shadow-xs"
        >
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-emerald-700/70 hover:text-emerald-900"
          >
            Dismiss
          </button>
        </div>
      )}

      {query.isError && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-xs">
          <AlertCircle aria-hidden="true" className="size-8 text-rose-500" />
          <h3 className="text-base font-semibold text-charcoal">Failed to load tickets</h3>
          <p className="text-xs text-charcoal/60">
            {errorMessage(query.error, "A network or server error occurred.")}
          </p>
          <button type="button" onClick={() => void query.refetch()} className={saleSecondaryButton}>
            <RefreshCw aria-hidden="true" className="size-3.5" />
            <span>Try again</span>
          </button>
        </div>
      )}

      {query.isLoading && !query.isError && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-10 text-xs text-charcoal/65 shadow-xs">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          <span>Loading tickets…</span>
        </div>
      )}

      {!query.isLoading && !query.isError && tickets.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-charcoal/10 bg-white p-12 text-center shadow-xs">
          <div className="flex size-12 items-center justify-center rounded-full bg-charcoal/5 text-charcoal/60">
            <Inbox aria-hidden="true" className="size-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-charcoal">
            {filtersActive ? "No tickets match these filters" : "No tickets yet"}
          </h3>
          <p className="mt-1 max-w-sm text-xs text-charcoal/60">
            {filtersActive
              ? "Try widening the status, priority, assignee or SLA filter."
              : "Open a ticket for a customer issue; its SLA clock starts immediately based on priority."}
          </p>
          {filtersActive && (
            <button type="button" onClick={resetFilters} className={`${saleSecondaryButton} mt-4`}>
              Clear filters
            </button>
          )}
        </div>
      )}

      {!query.isLoading && !query.isError && tickets.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-charcoal/10 bg-white shadow-xs">
            <table className="min-w-full text-left text-xs">
              <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/55">
                <tr>
                  <th scope="col" className="px-4 py-3">Ticket</th>
                  <th scope="col" className="px-4 py-3">Category</th>
                  <th scope="col" className="px-4 py-3">Priority</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">SLA</th>
                  <th scope="col" className="px-4 py-3">Opened</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal/5">
                {tickets.map((ticket) => (
                  <TicketRow
                    key={ticket.id}
                    ticket={ticket}
                    onOpen={() => setOpenTicketId(ticket.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <ApprovalPagination
            page={page}
            pageCount={pageCount}
            total={total}
            pageSize={PAGE_SIZE}
            itemName="tickets"
            onPageChange={setPage}
          />
        </>
      )}

      {openTicketId && (
        <TicketDetailDrawer
          ticketId={openTicketId}
          staffUsers={staffUsers}
          onClose={() => setOpenTicketId(null)}
        />
      )}

      {createOpen && (
        <CreateTicketModal
          onClose={() => setCreateOpen(false)}
          onCreated={(message) => {
            setCreateOpen(false);
            setPage(1);
            showNotice(message);
          }}
        />
      )}
    </div>
  );
}

function TicketRow({ ticket, onOpen }: { ticket: TicketItem; onOpen: () => void }) {
  const breached = isSlaBreached(ticket);
  return (
    <tr
      className="cursor-pointer align-middle transition-colors hover:bg-charcoal/[0.03]"
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      tabIndex={0}
      aria-label={`Open ticket ${ticket.ticket_number}`}
    >
      <td className="max-w-72 px-4 py-3">
        <p className="font-semibold whitespace-nowrap text-charcoal">{ticket.ticket_number}</p>
        <p className="mt-0.5 truncate text-charcoal/75" title={ticket.subject}>
          {ticket.subject}
        </p>
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-charcoal/75">
        {ticketCategoryLabel(ticket.category)}
      </td>
      <td className="px-4 py-3">
        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${ticketPriorityTone(ticket.priority)}`}>
          {ticketPriorityLabel(ticket.priority)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${ticketStatusTone(ticket.status)}`}>
          {ticketStatusLabel(ticket.status)}
        </span>
      </td>
      <td className="px-4 py-3 whitespace-nowrap">
        <span className={breached ? "font-semibold text-rose-700" : "text-charcoal/70"}>
          {slaCountdownLabel(ticket.sla_due_at)}
        </span>
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-charcoal/70">
        {formatDateTime(ticket.created_at)}
      </td>
    </tr>
  );
}

function ServiceDeskFilters({
  status,
  onStatusChange,
  priority,
  onPriorityChange,
  breachOnly,
  onBreachOnlyChange,
  assignedToId,
  onAssignedToChange,
  staffUsers,
}: {
  status: TicketStatus | "ALL";
  onStatusChange: (value: TicketStatus | "ALL") => void;
  priority: TicketPriority | "ALL";
  onPriorityChange: (value: TicketPriority | "ALL") => void;
  breachOnly: boolean;
  onBreachOnlyChange: (value: boolean) => void;
  assignedToId: string | "ALL";
  onAssignedToChange: (value: string | "ALL") => void;
  staffUsers: readonly { id: string; full_name: string }[];
}) {
  return (
    <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs">
      <div>
        <label htmlFor="desk-status-filter" className={saleLabelClasses}>
          Status
        </label>
        <select
          id="desk-status-filter"
          value={status}
          onChange={(event) => onStatusChange(event.target.value as TicketStatus | "ALL")}
          className={`${saleInputClasses} mt-1 min-w-36`}
        >
          <option value="ALL">All statuses</option>
          {TICKET_STATUSES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="desk-priority-filter" className={saleLabelClasses}>
          Priority
        </label>
        <select
          id="desk-priority-filter"
          value={priority}
          onChange={(event) => onPriorityChange(event.target.value as TicketPriority | "ALL")}
          className={`${saleInputClasses} mt-1 min-w-32`}
        >
          <option value="ALL">All priorities</option>
          {TICKET_PRIORITIES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="desk-assignee-filter" className={saleLabelClasses}>
          Assignee
        </label>
        <select
          id="desk-assignee-filter"
          value={assignedToId}
          onChange={(event) => onAssignedToChange(event.target.value)}
          className={`${saleInputClasses} mt-1 min-w-40`}
        >
          <option value="ALL">Any assignee</option>
          {staffUsers.map((member) => (
            <option key={member.id} value={member.id}>
              {member.full_name}
            </option>
          ))}
        </select>
      </div>
      <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-xs font-semibold text-rose-700">
        <input
          type="checkbox"
          checked={breachOnly}
          onChange={(event) => onBreachOnlyChange(event.target.checked)}
          className="size-3.5 rounded border-charcoal/30 accent-rose-600"
        />
        <AlertTriangle aria-hidden="true" className="size-3.5" />
        Past SLA only
      </label>
    </div>
  );
}
