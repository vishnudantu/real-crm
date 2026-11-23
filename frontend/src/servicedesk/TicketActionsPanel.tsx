import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LoaderCircle,
  LockKeyhole,
  MessageSquarePlus,
  SendHorizontal,
} from "lucide-react";
import type { UserItem } from "../admin/adminModel";
import {
  formatDateTime,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
} from "../admin/sales/salesBookingUi";
import { errorMessage } from "../shared/apiRequest";
import {
  addTicketComment,
  assignTicket,
  ticketKeys,
  updateTicketStatus,
} from "./serviceDeskApi";
import type { TicketDetail, TicketStatus } from "./serviceDeskModel";
import {
  MAX_TICKET_COMMENT_LENGTH,
  MAX_RESOLUTION_NOTE_LENGTH,
  TICKET_STATUSES,
  allowedNextStatuses,
  ticketStatusLabel,
  validateCommentBody,
} from "./serviceDeskModel";

interface TicketActionsPanelProps {
  ticket: TicketDetail;
  staffUsers: readonly UserItem[];
}

/** Comment composer, status workflow and assignment for the selected ticket.
 * Priority is intentionally absent: the API exposes no priority update. */
export function TicketActionsPanel({ ticket, staffUsers }: TicketActionsPanelProps) {
  return (
    <div className="flex flex-col gap-5">
      <TicketStatusForm ticket={ticket} />
      <TicketAssignmentForm ticket={ticket} staffUsers={staffUsers} />
      <TicketCommentForm ticketId={ticket.id} />
    </div>
  );
}

function TicketStatusForm({ ticket }: { ticket: TicketDetail }) {
  const queryClient = useQueryClient();
  const nextStatuses = allowedNextStatuses(ticket.status);
  const [nextStatus, setNextStatus] = useState<TicketStatus | "">(nextStatuses[0] ?? "");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  // After each update the allowed list shrinks; keep the select on a legal step.
  const selectedStatus =
    nextStatus && nextStatuses.includes(nextStatus) ? nextStatus : (nextStatuses[0] ?? "");

  const mutation = useMutation({
    mutationFn: () =>
      updateTicketStatus(ticket.id, selectedStatus as TicketStatus, note.trim() || null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ticketKeys.all });
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "The status could not be updated."));
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all });
    },
  });

  if (nextStatuses.length === 0) {
    return (
      <p className="text-xs text-charcoal/55">
        This ticket is {ticketStatusLabel(ticket.status).toLowerCase()} and has no further transitions.
      </p>
    );
  }

  const resolving = selectedStatus === "RESOLVED" || selectedStatus === "CLOSED";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!selectedStatus || mutation.isPending) return;
        setError(null);
        mutation.mutate();
      }}
      className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"
    >
      <h3 className="text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
        Move ticket
      </h3>
      <label htmlFor="ticket-next-status" className={`${saleLabelClasses} mt-3`}>
        New status
      </label>
      <select
        id="ticket-next-status"
        value={selectedStatus}
        onChange={(event) => setNextStatus(event.target.value as TicketStatus)}
        className={`${saleInputClasses} mt-1`}
      >
        {nextStatuses.map((status) => (
          <option key={status} value={status}>
            {TICKET_STATUSES.find((entry) => entry.value === status)?.label ?? status}
          </option>
        ))}
      </select>
      <label htmlFor="ticket-resolution-note" className={`${saleLabelClasses} mt-3`}>
        Resolution note{" "}
        {resolving && <span className="font-normal text-charcoal/45">(recommended)</span>}
      </label>
      <textarea
        id="ticket-resolution-note"
        rows={2}
        maxLength={MAX_RESOLUTION_NOTE_LENGTH}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="How was it fixed, or what happens next."
        className={`${saleInputClasses} mt-1 resize-y`}
      />
      {error && (
        <p role="alert" className="mt-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!selectedStatus || mutation.isPending}
        className={`${salePrimaryButton} mt-3 w-full`}
      >
        {mutation.isPending ? (
          <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
        ) : (
          <SendHorizontal aria-hidden="true" className="size-3.5" />
        )}
        <span>Update status</span>
      </button>
      <p className="mt-2 text-[10.5px] text-charcoal/50">
        Transitions are validated server-side; only the steps shown are allowed.
      </p>
    </form>
  );
}

function TicketAssignmentForm({
  ticket,
  staffUsers,
}: {
  ticket: TicketDetail;
  staffUsers: readonly UserItem[];
}) {
  const queryClient = useQueryClient();
  const [assignee, setAssignee] = useState(ticket.assigned_to_id ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (assignedToId: string) => assignTicket(ticket.id, assignedToId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ticketKeys.all });
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "The ticket could not be assigned."));
    },
  });

  if (staffUsers.length === 0) return null;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!assignee || mutation.isPending) return;
        setError(null);
        mutation.mutate(assignee);
      }}
      className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"
    >
      <label htmlFor="ticket-assignee" className={saleLabelClasses}>
        Assign to staff
      </label>
      <select
        id="ticket-assignee"
        value={assignee}
        onChange={(event) => setAssignee(event.target.value)}
        className={`${saleInputClasses} mt-1`}
      >
        <option value="">Choose a staff member…</option>
        {staffUsers.map((member) => (
          <option key={member.id} value={member.id}>
            {member.full_name} ({member.role.name === "ADMIN" ? "admin" : "sales"})
          </option>
        ))}
      </select>
      {error && (
        <p role="alert" className="mt-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!assignee || mutation.isPending}
        className={`${salePrimaryButton} mt-3 w-full`}
      >
        {mutation.isPending ? (
          <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
        ) : (
          <SendHorizontal aria-hidden="true" className="size-3.5" />
        )}
        <span>Assign ticket</span>
      </button>
    </form>
  );
}

export function TicketCommentThread({ ticket }: { ticket: TicketDetail }) {
  return (
    <ol className="space-y-3" aria-label="Comment thread">
      {ticket.comments.map((comment) => (
        <li
          key={comment.id}
          className={`rounded-xl border px-3.5 py-2.5 text-xs leading-5 ${
            comment.is_internal
              ? "border-amber-200 bg-amber-50/70 text-amber-950"
              : "border-charcoal/10 bg-white text-charcoal/85"
          }`}
        >
          <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold text-charcoal/50">
            {comment.is_internal && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-amber-800">
                <LockKeyhole aria-hidden="true" className="size-2.5" />
                Internal note
              </span>
            )}
            <time>{formatDateTime(comment.created_at)}</time>
          </div>
          <p className="whitespace-pre-wrap">{comment.body}</p>
        </li>
      ))}
      {ticket.comments.length === 0 && (
        <p className="rounded-xl border border-dashed border-charcoal/15 px-3.5 py-4 text-center text-xs text-charcoal/50">
          No comments yet — start the conversation or log an internal note.
        </p>
      )}
    </ol>
  );
}

function TicketCommentForm({ ticketId }: { ticketId: string }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => addTicketComment(ticketId, body.trim(), internal),
    onSuccess: async () => {
      setBody("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ticketKeys.all });
    },
    onError: (mutationError: unknown) => {
      setError(errorMessage(mutationError, "The comment could not be posted."));
    },
  });

  const validationError = validateCommentBody(body);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (validationError || mutation.isPending) return;
        mutation.mutate();
      }}
      className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"
    >
      <h3 className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-charcoal/50 uppercase">
        <MessageSquarePlus aria-hidden="true" className="size-3.5" />
        Add comment
      </h3>
      <label htmlFor="ticket-comment-body" className="sr-only">
        Comment body
      </label>
      <textarea
        id="ticket-comment-body"
        rows={3}
        maxLength={MAX_TICKET_COMMENT_LENGTH}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder={internal ? "Note for staff only…" : "Reply to the customer thread…"}
        className={`${saleInputClasses} mt-2 resize-y`}
      />
      <label className="mt-2 flex cursor-pointer items-center gap-2 text-[11px] font-medium text-charcoal/75">
        <input
          type="checkbox"
          checked={internal}
          onChange={(event) => setInternal(event.target.checked)}
          className="size-3.5 rounded border-charcoal/30 accent-forest"
        />
        <LockKeyhole aria-hidden="true" className="size-3 text-charcoal/50" />
        Internal note (staff only)
      </label>
      {(error || (body.trim() && validationError)) && (
        <p role="alert" className="mt-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
          {error ?? validationError}
        </p>
      )}
      <button
        type="submit"
        disabled={Boolean(validationError) || mutation.isPending}
        className={`${salePrimaryButton} mt-3 w-full`}
      >
        {mutation.isPending ? (
          <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />
        ) : (
          <SendHorizontal aria-hidden="true" className="size-3.5" />
        )}
        <span>Post {internal ? "internal note" : "comment"}</span>
      </button>
    </form>
  );
}
