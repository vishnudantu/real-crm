import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckSquare,
  Inbox,
  LoaderCircle,
  Plus,
  RefreshCw,
} from "lucide-react";
import { errorMessage } from "../shared/apiRequest";
import { fetchUsers } from "../admin/api";
import { useAdminUser } from "../admin/AdminAuthGuard";
import {
  formatDateTime,
  formatInr,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";
import { approvalKeys, fetchApprovals } from "./approvalsApi";
import type { ApprovalRequestItem, ApprovalStatus } from "./approvalsModel";
import {
  APPROVAL_STATUSES,
  isPending,
  totalPages,
} from "./approvalsModel";
import { ApprovalStatusChip, ApprovalPagination } from "./ApprovalsUi";
import { ApprovalDetailDrawer } from "./ApprovalDetailDrawer";
import { CreateApprovalRequestModal } from "./CreateApprovalRequestModal";

const PAGE_SIZE = 25;

/** /admin/approvals — staff approval queue: page, filter, create, decide. */
export function ApprovalsPage() {
  const { user } = useAdminUser();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<ApprovalStatus | "ALL">("ALL");
  const [requestType, setRequestType] = useState("");
  const [openRequest, setOpenRequest] = useState<ApprovalRequestItem | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const query = useQuery({
    queryKey: approvalKeys.list(page, PAGE_SIZE, status, requestType),
    queryFn: () => fetchApprovals({ page, pageSize: PAGE_SIZE, status, requestType }),
  });
  const pendingCountQuery = useQuery({
    queryKey: [...approvalKeys.all, "pending-count"],
    queryFn: () => fetchApprovals({ page: 1, pageSize: 1, status: "PENDING", requestType: "" }),
    staleTime: 30_000,
  });

  const isAdmin = user.role.name === "ADMIN";
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const pageCount = totalPages(total, PAGE_SIZE);
  // The server re-reads rows after each mutation, so keep the drawer in sync.
  const liveRequest =
    openRequest === null
      ? null
      : (items.find((item) => item.id === openRequest.id) ?? openRequest);

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice((prev) => (prev === message ? null : prev)), 4500);
  };

  const resetFilters = () => {
    setStatus("ALL");
    setRequestType("");
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-sans text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
            Approvals
          </h1>
          <p className="mt-1 text-sm text-charcoal/65">
            Staff requests awaiting a manager decision
            {typeof pendingCountQuery.data?.total === "number" && (
              <>
                {" · "}
                <span className="font-semibold text-charcoal">
                  {pendingCountQuery.data.total} pending
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
          aria-label="Create an approval request"
        >
          <Plus aria-hidden="true" className="size-4" />
          <span>New request</span>
        </button>
      </div>

      <ApprovalsFilters
        status={status}
        onStatusChange={(value) => {
          setStatus(value);
          setPage(1);
        }}
        requestType={requestType}
        onRequestTypeChange={(value) => {
          setRequestType(value);
          setPage(1);
        }}
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
          <h3 className="text-base font-semibold text-charcoal">Failed to load approvals</h3>
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
          <span>Loading approval requests…</span>
        </div>
      )}

      {!query.isLoading && !query.isError && items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-charcoal/10 bg-white p-12 text-center shadow-xs">
          <div className="flex size-12 items-center justify-center rounded-full bg-charcoal/5 text-charcoal/60">
            {status === "PENDING" ? (
              <CheckSquare aria-hidden="true" className="size-6" />
            ) : (
              <Inbox aria-hidden="true" className="size-6" />
            )}
          </div>
          <h3 className="mt-3 text-base font-semibold text-charcoal">
            {status === "ALL" && !requestType
              ? "No approval requests yet"
              : "No requests match these filters"}
          </h3>
          <p className="mt-1 max-w-sm text-xs text-charcoal/60">
            {status === "ALL" && !requestType
              ? "Raise a discount, site-visit car or document approval and it appears here for a manager to decide."
              : "Try widening the status or clearing the request type filter."}
          </p>
          {(status !== "ALL" || requestType) && (
            <button type="button" onClick={resetFilters} className={`${saleSecondaryButton} mt-4`}>
              Clear filters
            </button>
          )}
        </div>
      )}

      {!query.isLoading && !query.isError && items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-charcoal/10 bg-white shadow-xs">
            <table className="min-w-full text-left text-xs">
              <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/55">
                <tr>
                  <th scope="col" className="px-4 py-3">Type</th>
                  <th scope="col" className="px-4 py-3">Reference</th>
                  <th scope="col" className="px-4 py-3">Reason</th>
                  <th scope="col" className="px-4 py-3">Amount</th>
                  <th scope="col" className="px-4 py-3">Raised</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal/5">
                {items.map((request) => (
                  <ApprovalRow
                    key={request.id}
                    request={request}
                    onOpen={() => setOpenRequest(request)}
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
            itemName="requests"
            onPageChange={setPage}
          />
        </>
      )}

      {liveRequest && (
        <ApprovalDetailDrawer
          request={liveRequest}
          currentUserId={user.id}
          isAdmin={isAdmin}
          onClose={() => setOpenRequest(null)}
          onMessage={showNotice}
        />
      )}

      {createOpen && (
        <CreateRequestFlow
          onClose={() => setCreateOpen(false)}
          onCreated={(message) => {
            setCreateOpen(false);
            void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
            showNotice(message);
          }}
        />
      )}
    </div>
  );
}

function ApprovalRow({
  request,
  onOpen,
}: {
  request: ApprovalRequestItem;
  onOpen: () => void;
}) {
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
      aria-label={`Open ${request.request_type} approval details`}
    >
      <td className="px-4 py-3 font-semibold whitespace-nowrap text-charcoal">
        {request.request_type}
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-charcoal/70">
        <span className="text-charcoal/50">{request.reference_type}</span>{" "}
        <span className="font-mono text-[11px]" title={request.reference_id}>
          {request.reference_id.slice(0, 8)}…
        </span>
      </td>
      <td className="max-w-64 px-4 py-3">
        <p className="truncate text-charcoal/75" title={request.reason}>
          {request.reason}
        </p>
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-charcoal/75">
        {request.amount_paise !== null ? formatInr(request.amount_paise) : "—"}
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-charcoal/70">
        {formatDateTime(request.created_at)}
      </td>
      <td className="px-4 py-3">
        <ApprovalStatusChip status={request.status} />
        {isPending(request) && (
          <span className="sr-only"> — open to decide</span>
        )}
      </td>
    </tr>
  );
}

function ApprovalsFilters({
  status,
  onStatusChange,
  requestType,
  onRequestTypeChange,
}: {
  status: ApprovalStatus | "ALL";
  onStatusChange: (value: ApprovalStatus | "ALL") => void;
  requestType: string;
  onRequestTypeChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs">
      <div>
        <label htmlFor="approvals-status-filter" className={saleLabelClasses}>
          Status
        </label>
        <select
          id="approvals-status-filter"
          value={status}
          onChange={(event) => onStatusChange(event.target.value as ApprovalStatus | "ALL")}
          className={`${saleInputClasses} mt-1 min-w-36`}
        >
          <option value="ALL">All statuses</option>
          {APPROVAL_STATUSES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="approvals-type-filter" className={saleLabelClasses}>
          Request type
        </label>
        <input
          id="approvals-type-filter"
          type="search"
          maxLength={48}
          value={requestType}
          onChange={(event) => onRequestTypeChange(event.target.value)}
          placeholder="e.g. DISCOUNT"
          className={`${saleInputClasses} mt-1 min-w-40 font-mono uppercase`}
        />
      </div>
      <p className="pb-2.5 text-[11px] text-charcoal/50">
        Type filter is an exact match; backend max 48 chars.
      </p>
    </div>
  );
}

/** Loads active admins (for the optional approver picker) then shows the form. */
function CreateRequestFlow({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (message: string) => void;
}) {
  const adminsQuery = useQuery({
    queryKey: ["admin", "users", "active-admins"],
    queryFn: () => fetchUsers({ page: 1, pageSize: 100, role: "ADMIN", status: "ACTIVE" }),
    staleTime: 120_000,
  });
  return (
    <CreateApprovalRequestModal
      admins={adminsQuery.data?.items ?? []}
      onClose={onClose}
      onCreated={onCreated}
    />
  );
}
