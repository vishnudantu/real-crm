import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  FileText,
  LoaderCircle,
  Mail,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { errorMessage } from "../../shared/apiRequest";
import { useModalFocus } from "../../shared/useModalFocus";
import {
  fetchSaleLedger,
  sendDemandLetter,
  updateCommission,
  updateSaleBooking,
} from "./salesBookingApi";
import type {
  CommissionItem,
  InstallmentItem,
  SaleBookingItem,
  SaleStatus,
} from "./salesBookingModel";
import {
  COMMISSION_STATUSES,
  SALE_STATUSES,
  commissionStatusBadgeClass,
  installmentStatusBadgeClass,
  saleStatusBadgeClass,
} from "./salesBookingModel";
import {
  formatDateTime,
  formatInr,
  formatShortDate,
  saleCardClasses,
  saleDangerButton,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "./salesBookingUi";
import { CreatePlanModal } from "./CreatePlanModal";
import { CreateCommissionModal } from "./CreateCommissionModal";
import { RecordReceiptModal } from "./RecordReceiptModal";

interface BookingLedgerDrawerProps {
  booking: SaleBookingItem;
  leadName: string;
  projectName: string;
  onClose: () => void;
  onChanged: (message: string) => Promise<void> | void;
}

export function BookingLedgerDrawer({
  booking,
  leadName,
  projectName,
  onClose,
  onChanged,
}: BookingLedgerDrawerProps) {
  const queryClient = useQueryClient();
  const dialogRef = useModalFocus<HTMLDivElement>(onClose);
  const [createPlanOpen, setCreatePlanOpen] = useState(false);
  const [createCommissionOpen, setCreateCommissionOpen] = useState(false);
  const [receiptInstallment, setReceiptInstallment] =
    useState<InstallmentItem | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const {
    data: ledger,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["admin", "sale-bookings", booking.id, "ledger"],
    queryFn: () => fetchSaleLedger(booking.id),
  });

  const statusMutation = useMutation({
    mutationFn: (status: SaleStatus) =>
      updateSaleBooking(booking.id, { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["admin", "sale-bookings"],
      });
      await onChanged("Booking status updated.");
      await refetch();
    },
    onError: (err: unknown) => {
      setActionError(errorMessage(err, "Failed to update status."));
    },
  });

  const commissionMutation = useMutation({
    mutationFn: (input: { id: string; status: CommissionItem["status"] }) =>
      updateCommission(input.id, { status: input.status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["admin", "sale-bookings", booking.id, "ledger"],
      });
      await refetch();
    },
    onError: (err: unknown) => {
      setActionError(errorMessage(err, "Failed to update commission."));
    },
  });

  const demandLetterMutation = useMutation({
    mutationFn: (installmentId: string) => sendDemandLetter(installmentId),
    onSuccess: async () => {
      await refetch();
      await onChanged("Demand letter dispatched.");
    },
    onError: (err: unknown) => {
      setActionError(errorMessage(err, "Failed to send demand letter."));
    },
  });

  const currentStatus = ledger?.booking.status ?? booking.status;
  const consideration = ledger?.booking.consideration_paise ?? booking.consideration_paise;
  const collected = ledger?.collected_paise ?? 0;
  const outstanding = ledger?.outstanding_paise ?? 0;
  const installments = ledger?.installments ?? [];
  const receipts = ledger?.receipts ?? [];
  const commissions = ledger?.commissions ?? [];
  const plans = ledger?.plans ?? [];

  const handleDemandLetter = async (installmentId: string) => {
    setActionError(null);
    setBusyId(installmentId);
    try {
      await demandLetterMutation.mutateAsync(installmentId);
    } finally {
      setBusyId(null);
    }
  };

  const handleCommissionStatus = async (
    commission: CommissionItem,
    status: CommissionItem["status"],
  ) => {
    setActionError(null);
    setBusyId(commission.id);
    try {
      await commissionMutation.mutateAsync({ id: commission.id, status });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-end bg-charcoal/45 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Ledger for unit ${booking.unit_number}`}
        className="flex h-full w-full max-w-3xl flex-col overflow-hidden border-l border-charcoal/10 bg-[#FAFAF7] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-charcoal/10 bg-[#FAFAF7] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-charcoal">
              Unit {booking.unit_number} · {projectName}
            </h2>
            <p className="mt-0.5 text-[11px] text-charcoal/60">{leadName}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close ledger"
            className="rounded-lg p-1.5 text-charcoal/50 hover:bg-charcoal/5 hover:text-charcoal"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {actionError && (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
            >
              {actionError}
            </p>
          )}

          {/* Summary */}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className={`${saleCardClasses} p-3`}>
              <p className="text-[10px] uppercase tracking-wider text-charcoal/55">
                Consideration
              </p>
              <p className="mt-1 text-sm font-semibold text-charcoal">
                {formatInr(consideration)}
              </p>
            </div>
            <div className={`${saleCardClasses} p-3`}>
              <p className="text-[10px] uppercase tracking-wider text-charcoal/55">
                Collected
              </p>
              <p className="mt-1 text-sm font-semibold text-emerald-700">
                {formatInr(collected)}
              </p>
            </div>
            <div className={`${saleCardClasses} p-3`}>
              <p className="text-[10px] uppercase tracking-wider text-charcoal/55">
                Outstanding
              </p>
              <p className="mt-1 text-sm font-semibold text-amber-700">
                {formatInr(outstanding)}
              </p>
            </div>
            <div className={`${saleCardClasses} p-3`}>
              <label
                htmlFor="ledger-status"
                className="text-[10px] uppercase tracking-wider text-charcoal/55"
              >
                Status
              </label>
              <select
                id="ledger-status"
                value={currentStatus}
                onChange={(event) => {
                  setActionError(null);
                  statusMutation.mutate(event.target.value as SaleStatus);
                }}
                disabled={statusMutation.isPending}
                className={`mt-1 w-full rounded-lg border px-2 py-1 text-[11px] font-semibold ${saleStatusBadgeClass(currentStatus)}`}
              >
                {SALE_STATUSES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Meta */}
          <dl className="mt-4 grid gap-2 text-[11px] sm:grid-cols-3">
            <div>
              <dt className="text-charcoal/55">Configuration</dt>
              <dd className="mt-0.5 font-medium text-charcoal">
                {booking.configuration ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-charcoal/55">Carpet area</dt>
              <dd className="mt-0.5 font-medium text-charcoal">
                {booking.carpet_area_sqft
                  ? `${booking.carpet_area_sqft} sqft`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-charcoal/55">Booked on</dt>
              <dd className="mt-0.5 font-medium text-charcoal">
                {formatShortDate(booking.booked_on)}
              </dd>
            </div>
          </dl>

          {isLoading && (
            <div className="mt-6 flex items-center gap-2 text-xs text-charcoal/65">
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              <span>Loading ledger…</span>
            </div>
          )}

          {isError && (
            <div className="mt-6 flex flex-col items-center gap-2 rounded-2xl border border-rose-200 bg-white p-6 text-center">
              <AlertCircle aria-hidden="true" className="size-6 text-rose-500" />
              <p className="text-xs text-charcoal/70">
                {(error as Error)?.message ?? "Failed to load ledger."}
              </p>
              <button
                type="button"
                onClick={() => refetch()}
                className={saleSecondaryButton}
              >
                <RefreshCw aria-hidden="true" className="size-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {!isLoading && !isError && ledger && (
            <>
              {/* Installments */}
              <section className="mt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-charcoal">
                      Installments
                    </h3>
                    <p className="text-[11px] text-charcoal/55">
                      {plans.length} plan{plans.length === 1 ? "" : "s"} ·{" "}
                      {installments.length} installment
                      {installments.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCreatePlanOpen(true)}
                    className={salePrimaryButton}
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    <span>New plan</span>
                  </button>
                </div>

                {installments.length === 0 ? (
                  <div className="mt-3 rounded-xl border border-charcoal/10 bg-white p-6 text-center text-xs text-charcoal/60">
                    No payment plan yet. Create a plan to track installments.
                  </div>
                ) : (
                  <div className="mt-3 overflow-x-auto rounded-xl border border-charcoal/10 bg-white">
                    <table className="min-w-full text-left text-[11px]">
                      <thead className="border-b border-charcoal/10 bg-[#FAFAF7] text-[10px] uppercase tracking-wider text-charcoal/55">
                        <tr>
                          <th scope="col" className="px-3 py-2">#</th>
                          <th scope="col" className="px-3 py-2">Milestone</th>
                          <th scope="col" className="px-3 py-2">Due</th>
                          <th scope="col" className="px-3 py-2">Amount</th>
                          <th scope="col" className="px-3 py-2">Paid</th>
                          <th scope="col" className="px-3 py-2">Outstanding</th>
                          <th scope="col" className="px-3 py-2">Status</th>
                          <th scope="col" className="px-3 py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-charcoal/5">
                        {installments.map((row) => (
                          <tr key={row.id} className="align-top">
                            <td className="px-3 py-2 font-medium text-charcoal/70">
                              {row.sequence_no}
                            </td>
                            <td className="px-3 py-2">
                              <div className="font-medium text-charcoal">
                                {row.milestone}
                              </div>
                              {row.demand_letter_sent_at && (
                                <div className="mt-0.5 text-[10px] text-charcoal/55">
                                  Demand letter {formatDateTime(row.demand_letter_sent_at)}
                                </div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-charcoal/75">
                              {formatShortDate(row.due_on)}
                            </td>
                            <td className="px-3 py-2 font-medium text-charcoal">
                              {formatInr(row.amount_paise)}
                            </td>
                            <td className="px-3 py-2 text-emerald-700">
                              {formatInr(row.paid_paise)}
                            </td>
                            <td className="px-3 py-2 text-amber-700">
                              {formatInr(row.outstanding_paise)}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${installmentStatusBadgeClass(row.status)}`}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right">
                              <div className="flex flex-wrap justify-end gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => setReceiptInstallment(row)}
                                  disabled={row.outstanding_paise <= 0}
                                  className={saleSecondaryButton}
                                >
                                  <Plus aria-hidden="true" className="size-3" />
                                  <span>Receipt</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDemandLetter(row.id)}
                                  disabled={busyId === row.id}
                                  className={saleDangerButton}
                                  aria-label={`Send demand letter for ${row.milestone}`}
                                >
                                  {busyId === row.id ? (
                                    <LoaderCircle
                                      aria-hidden="true"
                                      className="size-3 animate-spin"
                                    />
                                  ) : (
                                    <Mail aria-hidden="true" className="size-3" />
                                  )}
                                  <span>Demand</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Receipts */}
              <section className="mt-6">
                <h3 className="text-sm font-semibold text-charcoal">Receipts</h3>
                {receipts.length === 0 ? (
                  <div className="mt-3 rounded-xl border border-charcoal/10 bg-white p-6 text-center text-xs text-charcoal/60">
                    No receipts recorded yet.
                  </div>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {receipts.map((receipt) => (
                      <li
                        key={receipt.id}
                        className={`${saleCardClasses} flex items-start justify-between gap-3 p-3`}
                      >
                        <div>
                          <p className="text-xs font-semibold text-charcoal">
                            {receipt.receipt_number}
                          </p>
                          <p className="mt-0.5 text-[11px] text-charcoal/60">
                            {receipt.channel}
                            {receipt.reference ? ` · ${receipt.reference}` : ""}
                          </p>
                          <p className="mt-0.5 text-[10.5px] text-charcoal/55">
                            Paid {formatDateTime(receipt.paid_at)}
                          </p>
                          {receipt.notes && (
                            <p className="mt-1 text-[11px] text-charcoal/70">
                              {receipt.notes}
                            </p>
                          )}
                        </div>
                        <p className="text-sm font-semibold text-emerald-700">
                          {formatInr(receipt.amount_paise)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Commissions */}
              <section className="mt-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-charcoal">
                    Broker commissions
                  </h3>
                  <button
                    type="button"
                    onClick={() => setCreateCommissionOpen(true)}
                    className={saleSecondaryButton}
                  >
                    <Plus aria-hidden="true" className="size-3.5" />
                    <span>Add</span>
                  </button>
                </div>

                {commissions.length === 0 ? (
                  <div className="mt-3 rounded-xl border border-charcoal/10 bg-white p-6 text-center text-xs text-charcoal/60">
                    No broker payouts yet.
                  </div>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {commissions.map((commission) => (
                      <li
                        key={commission.id}
                        className={`${saleCardClasses} p-3`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-charcoal">
                              {commission.broker_name}
                            </p>
                            {commission.broker_phone && (
                              <p className="text-[11px] text-charcoal/60">
                                {commission.broker_phone}
                              </p>
                            )}
                            <p className="mt-1 text-[11px] text-charcoal/55">
                              {typeof commission.basis?.percent === "number"
                                ? `${commission.basis.percent}% of consideration · `
                                : ""}
                              Created {formatDateTime(commission.created_at)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-semibold text-charcoal">
                              {formatInr(commission.amount_paise)}
                            </p>
                            <span
                              className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${commissionStatusBadgeClass(commission.status)}`}
                            >
                              {commission.status}
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2 border-t border-charcoal/5 pt-2">
                          <div className="flex items-center gap-2">
                            <FileText
                              aria-hidden="true"
                              className="size-3 text-charcoal/40"
                            />
                            <span className="text-[11px] text-charcoal/60">
                              {commission.paid_at
                                ? `Paid ${formatDateTime(commission.paid_at)}`
                                : "Awaiting payout"}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <label
                              htmlFor={`commission-status-${commission.id}`}
                              className={saleLabelClasses}
                            >
                              <span className="sr-only">
                                Commission status for {commission.broker_name}
                              </span>
                            </label>
                            <select
                              id={`commission-status-${commission.id}`}
                              value={commission.status}
                              onChange={(event) =>
                                handleCommissionStatus(
                                  commission,
                                  event.target.value as CommissionItem["status"],
                                )
                              }
                              disabled={busyId === commission.id}
                              className={`${saleInputClasses} mt-0 w-auto min-w-28 py-1.5 text-[11px]`}
                            >
                              {COMMISSION_STATUSES.map((entry) => (
                                <option key={entry.value} value={entry.value}>
                                  {entry.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </div>

      {createPlanOpen && (
        <CreatePlanModal
          bookingId={booking.id}
          considerationPaise={consideration}
          onClose={() => setCreatePlanOpen(false)}
          onCreated={async () => {
            setCreatePlanOpen(false);
            await refetch();
            await onChanged("Payment plan created.");
          }}
        />
      )}

      {createCommissionOpen && (
        <CreateCommissionModal
          bookingId={booking.id}
          considerationPaise={consideration}
          onClose={() => setCreateCommissionOpen(false)}
          onCreated={async () => {
            setCreateCommissionOpen(false);
            await refetch();
            await onChanged("Broker commission added.");
          }}
        />
      )}

      {receiptInstallment && (
        <RecordReceiptModal
          installment={receiptInstallment}
          onClose={() => setReceiptInstallment(null)}
          onRecorded={async () => {
            setReceiptInstallment(null);
            await refetch();
            await onChanged("Receipt recorded.");
          }}
        />
      )}
    </div>
  );
}
