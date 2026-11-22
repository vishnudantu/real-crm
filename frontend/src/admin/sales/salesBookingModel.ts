export type SaleStatus =
  | "BOOKED"
  | "AGREEMENT_PENDING"
  | "AGREEMENT_SIGNED"
  | "PAYMENTS_IN_PROGRESS"
  | "POSSESSION_READY"
  | "CLOSED"
  | "CANCELLED";

export type PaymentPlanType = "CONSTRUCTION_LINKED" | "TIME_LINKED" | "HYBRID";

export type InstallmentStatus =
  | "PENDING"
  | "DUE"
  | "PART_PAID"
  | "PAID"
  | "OVERDUE"
  | "WAIVED";

export type ReceiptChannel =
  | "UPI"
  | "CHEQUE"
  | "NEFT"
  | "CASH"
  | "CARD"
  | "LOAN_DISBURSAL";

export type CommissionStatus = "PENDING" | "PAYABLE" | "PAID" | "REVERSED";

export type SaleBookingItem = {
  id: string;
  tenant_id: string;
  lead_id: string;
  project_id: string;
  customer_id: string | null;
  unit_number: string;
  configuration: string | null;
  carpet_area_sqft: number | null;
  consideration_paise: number;
  status: SaleStatus;
  booked_on: string;
  agreement_date: string | null;
  expected_possession: string | null;
  created_at: string;
};

export type SaleBookingListResponse = {
  items: SaleBookingItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type CreateSaleBookingPayload = {
  lead_id: string;
  unit_number: string;
  configuration?: string | null;
  carpet_area_sqft?: number | null;
  consideration_paise: number;
  booked_on?: string | null;
};

export type UpdateSaleBookingPayload = {
  status?: SaleStatus;
  agreement_date?: string | null;
  expected_possession?: string | null;
  unit_number?: string;
  carpet_area_sqft?: number | null;
};

export type PaymentPlanItem = {
  id: string;
  sale_booking_id: string;
  name: string;
  plan_type: PaymentPlanType;
  is_active: boolean;
  created_at: string;
};

export type InstallmentItem = {
  id: string;
  plan_id: string;
  sequence_no: number;
  milestone: string;
  amount_paise: number;
  due_on: string;
  status: InstallmentStatus;
  demand_letter_sent_at: string | null;
  paid_paise: number;
  outstanding_paise: number;
};

export type ReceiptItem = {
  id: string;
  installment_id: string;
  receipt_number: string;
  amount_paise: number;
  channel: ReceiptChannel;
  reference: string | null;
  received_by_id: string | null;
  paid_at: string;
  notes: string | null;
  voided_at: string | null;
  voided_by_id: string | null;
  void_reason: string | null;
};

export type CommissionItem = {
  id: string;
  sale_booking_id: string;
  broker_name: string;
  broker_phone: string | null;
  basis: Record<string, unknown>;
  amount_paise: number;
  status: CommissionStatus;
  paid_at: string | null;
  created_at: string;
};

export type SaleLedgerResponse = {
  booking: SaleBookingItem;
  plans: PaymentPlanItem[];
  installments: InstallmentItem[];
  receipts: ReceiptItem[];
  commissions: CommissionItem[];
  collected_paise: number;
  outstanding_paise: number;
};

export type CreatePaymentPlanPayload = {
  name: string;
  plan_type: PaymentPlanType;
  installments: {
    milestone: string;
    amount_paise: number;
    due_on: string;
  }[];
};

export type CreateReceiptPayload = {
  installment_id: string;
  amount_paise: number;
  channel: ReceiptChannel;
  reference?: string | null;
  notes?: string | null;
  paid_at?: string | null;
};

export type CreateCommissionPayload = {
  broker_name: string;
  broker_phone?: string | null;
  amount_paise: number;
  basis?: Record<string, unknown>;
};

export type UpdateCommissionPayload = {
  status: CommissionStatus;
};

/**
 * Operational corrections on an open installment. ``PAID`` and ``WAIVED`` are
 * deliberately unreachable: the backend rejects them — PAID requires a receipt
 * posting and WAIVED belongs to a future waiver workflow.
 */
export type InstallmentUpdatePayload = {
  due_on?: string;
  amount_paise?: number;
  status?: Exclude<InstallmentStatus, "PAID" | "WAIVED">;
};

export const SALE_STATUSES: { value: SaleStatus; label: string }[] = [
  { value: "BOOKED", label: "Booked" },
  { value: "AGREEMENT_PENDING", label: "Agreement Pending" },
  { value: "AGREEMENT_SIGNED", label: "Agreement Signed" },
  { value: "PAYMENTS_IN_PROGRESS", label: "Payments In Progress" },
  { value: "POSSESSION_READY", label: "Possession Ready" },
  { value: "CLOSED", label: "Closed" },
  { value: "CANCELLED", label: "Cancelled" },
];

export const PLAN_TYPES: { value: PaymentPlanType; label: string }[] = [
  { value: "CONSTRUCTION_LINKED", label: "Construction Linked" },
  { value: "TIME_LINKED", label: "Time Linked" },
  { value: "HYBRID", label: "Hybrid" },
];

export const RECEIPT_CHANNELS: { value: ReceiptChannel; label: string }[] = [
  { value: "UPI", label: "UPI" },
  { value: "CHEQUE", label: "Cheque" },
  { value: "NEFT", label: "NEFT" },
  { value: "CASH", label: "Cash" },
  { value: "CARD", label: "Card" },
  { value: "LOAN_DISBURSAL", label: "Loan Disbursal" },
];

export const COMMISSION_STATUSES: { value: CommissionStatus; label: string }[] = [
  { value: "PENDING", label: "Pending" },
  { value: "PAYABLE", label: "Payable" },
  { value: "PAID", label: "Paid" },
  { value: "REVERSED", label: "Reversed" },
];

export function saleStatusLabel(status: string): string {
  return (
    SALE_STATUSES.find((entry) => entry.value === status)?.label ??
    status
      .toLowerCase()
      .split("_")
      .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
      .join(" ")
  );
}

export function saleStatusBadgeClass(status: string): string {
  switch (status) {
    case "CLOSED":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "PAYMENTS_IN_PROGRESS":
    case "AGREEMENT_SIGNED":
      return "border-blue-200 bg-blue-50 text-blue-800";
    case "POSSESSION_READY":
      return "border-teal-200 bg-teal-50 text-teal-800";
    case "CANCELLED":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "AGREEMENT_PENDING":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "BOOKED":
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}

export function installmentStatusBadgeClass(status: string): string {
  switch (status) {
    case "PAID":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "PART_PAID":
      return "border-blue-200 bg-blue-50 text-blue-800";
    case "OVERDUE":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "DUE":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "WAIVED":
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/70";
    case "PENDING":
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}

export function commissionStatusBadgeClass(status: string): string {
  switch (status) {
    case "PAID":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "PAYABLE":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "REVERSED":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "PENDING":
    default:
      return "border-charcoal/15 bg-charcoal/5 text-charcoal/80";
  }
}
