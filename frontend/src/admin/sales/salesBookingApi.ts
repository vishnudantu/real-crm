import { clearSession, getSession } from "../../auth/session";
import { bearerRequest } from "../../shared/apiRequest";
import type {
  CommissionItem,
  CreateCommissionPayload,
  CreatePaymentPlanPayload,
  CreateReceiptPayload,
  CreateSaleBookingPayload,
  InstallmentItem,
  InstallmentUpdatePayload,
  PaymentPlanItem,
  ReceiptItem,
  SaleBookingItem,
  SaleBookingListResponse,
  SaleLedgerResponse,
  SaleStatus,
  UpdateCommissionPayload,
  UpdateSaleBookingPayload,
} from "./salesBookingModel";

const SESSION = { getToken: getSession, clearToken: clearSession };

export type FetchSaleBookingsParams = {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: SaleStatus | "ALL";
  projectId?: string;
};

export function fetchSaleBookings(
  params: FetchSaleBookingsParams = {},
): Promise<SaleBookingListResponse> {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  query.set("page_size", String(params.pageSize ?? 10));
  if (params.search?.trim()) query.set("search", params.search.trim());
  if (params.status && params.status !== "ALL") {
    query.set("status", params.status);
  }
  if (params.projectId && params.projectId !== "ALL") {
    query.set("project_id", params.projectId);
  }
  return bearerRequest<SaleBookingListResponse>(
    `/sales-bookings?${query.toString()}`,
    SESSION,
  );
}

export function fetchSaleBooking(bookingId: string): Promise<SaleBookingItem> {
  return bearerRequest<SaleBookingItem>(`/sales-bookings/${bookingId}`, SESSION);
}

export function createSaleBooking(
  payload: CreateSaleBookingPayload,
): Promise<SaleBookingItem> {
  return bearerRequest<SaleBookingItem>("/sales-bookings", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSaleBooking(
  bookingId: string,
  payload: UpdateSaleBookingPayload,
): Promise<SaleBookingItem> {
  return bearerRequest<SaleBookingItem>(`/sales-bookings/${bookingId}`, SESSION, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function fetchSaleLedger(bookingId: string): Promise<SaleLedgerResponse> {
  return bearerRequest<SaleLedgerResponse>(
    `/sales-bookings/${bookingId}/ledger`,
    SESSION,
  );
}

export function createPaymentPlan(
  bookingId: string,
  payload: CreatePaymentPlanPayload,
): Promise<PaymentPlanItem> {
  return bearerRequest<PaymentPlanItem>(
    `/sales-bookings/${bookingId}/plans`,
    SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function recordReceipt(payload: CreateReceiptPayload): Promise<ReceiptItem> {
  return bearerRequest<ReceiptItem>("/sales-bookings/receipts", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sendDemandLetter(installmentId: string): Promise<void> {
  return bearerRequest<void>(
    `/sales-bookings/installments/${installmentId}/demand-letter`,
    SESSION,
    { method: "POST" },
  );
}

export function updateInstallment(
  installmentId: string,
  payload: InstallmentUpdatePayload,
): Promise<InstallmentItem> {
  return bearerRequest<InstallmentItem>(
    `/sales-bookings/installments/${installmentId}`,
    SESSION,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function voidReceipt(receiptId: string, reason: string): Promise<ReceiptItem> {
  return bearerRequest<ReceiptItem>(
    `/sales-bookings/receipts/${receiptId}/void`,
    SESSION,
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}

export function createCommission(
  bookingId: string,
  payload: CreateCommissionPayload,
): Promise<CommissionItem> {
  return bearerRequest<CommissionItem>(
    `/sales-bookings/${bookingId}/commissions`,
    SESSION,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function updateCommission(
  commissionId: string,
  payload: UpdateCommissionPayload,
): Promise<CommissionItem> {
  return bearerRequest<CommissionItem>(
    `/sales-bookings/commissions/${commissionId}`,
    SESSION,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}
