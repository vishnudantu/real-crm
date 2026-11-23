import { ChevronLeft, ChevronRight } from "lucide-react";
import { saleSecondaryButton } from "../admin/sales/salesBookingUi";
import type { ApprovalStatus } from "./approvalsModel";
import { approvalStatusLabel, approvalStatusTone } from "./approvalsModel";

export function ApprovalStatusChip({ status }: { status: ApprovalStatus | string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${approvalStatusTone(status)}`}
    >
      {approvalStatusLabel(status)}
    </span>
  );
}

export function ApprovalPagination({
  page,
  pageCount,
  total,
  pageSize,
  itemName,
  onPageChange,
}: {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  itemName: string;
  onPageChange: (page: number) => void;
}) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-charcoal/10 bg-white px-5 py-3.5 text-xs text-charcoal/70 shadow-xs sm:flex-row">
      <div>
        Showing <span className="font-semibold text-charcoal">{start}</span> to{" "}
        <span className="font-semibold text-charcoal">{end}</span> of{" "}
        <span className="font-semibold text-charcoal">{total}</span> {itemName}
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className={`${saleSecondaryButton} disabled:opacity-40`}
          aria-label="Previous page"
        >
          <ChevronLeft aria-hidden="true" className="size-3.5" />
          <span>Previous</span>
        </button>
        <div className="px-2 text-xs font-semibold text-charcoal">
          Page {page} of {pageCount}
        </div>
        <button
          type="button"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
          className={`${saleSecondaryButton} disabled:opacity-40`}
          aria-label="Next page"
        >
          <span>Next</span>
          <ChevronRight aria-hidden="true" className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
