import { clearSession, getSession } from "../auth/session";
import { bearerRequest } from "../shared/apiRequest";
import type {
  BankTransaction,
  IngestRequest,
  IngestResponse,
  SuggestMatchesResponse,
  TransactionListResponse,
  TransactionStatus,
} from "./model";

const SESSION = { getToken: getSession, clearToken: clearSession };

export const reconciliationKeys = {
  all: ["admin", "reconciliation"] as const,
  list: (status: TransactionStatus | "ALL", account: string) =>
    ["admin", "reconciliation", "transactions", { status, account }] as const,
};

export function fetchTransactions(
  status: TransactionStatus | "ALL",
  account: string,
): Promise<TransactionListResponse> {
  const query = new URLSearchParams();
  if (status !== "ALL") query.set("status", status);
  if (account.trim()) query.set("account_label", account.trim());
  const suffix = query.size ? `?${query}` : "";
  return bearerRequest<TransactionListResponse>(`/reconciliation/transactions${suffix}`, SESSION);
}

export function ingestTransactions(payload: IngestRequest): Promise<IngestResponse> {
  return bearerRequest<IngestResponse>("/reconciliation/ingest", SESSION, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function suggestMatches(): Promise<SuggestMatchesResponse> {
  return bearerRequest<SuggestMatchesResponse>("/reconciliation/suggest-matches", SESSION, {
    method: "POST",
  });
}

export function ignoreTransaction(transactionId: string): Promise<BankTransaction> {
  return bearerRequest<BankTransaction>(
    `/reconciliation/transactions/${transactionId}/ignore`,
    SESSION,
    { method: "POST" },
  );
}
