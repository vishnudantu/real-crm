export type TransactionStatus = "UNMATCHED" | "MATCHED" | "IGNORED";

export interface BankTransaction {
  id: string;
  account_label: string;
  utr: string;
  amount_paise: number;
  txn_date: string;
  payer_name: string | null;
  payer_detail: string | null;
  status: TransactionStatus;
  matched_installment_id: string | null;
  matched_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionListResponse {
  items: BankTransaction[];
  total: number;
}

export interface BankRowInput {
  utr: string;
  amount_paise: number;
  txn_date: string;
  payer_name: string | null;
  payer_detail: string | null;
}

export interface IngestRequest {
  account_label: string;
  rows: BankRowInput[];
}

export interface IngestResponse {
  created: number;
  duplicates: number;
  errors: string[];
}

export interface SuggestMatchesResponse {
  matched: number;
  suggested: number;
  still_unmatched: number;
}

export function transactionStatusTone(status: string): string {
  if (status === "MATCHED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "IGNORED") return "border-charcoal/15 bg-charcoal/5 text-charcoal/55";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

/** Parse comma/newline separated UTR, rupees, YYYY-MM-DD, payer, detail rows. */
export function parseBankRows(text: string): BankRowInput[] {
  const rows = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  return rows.map((line, index) => {
    const columns = line.split(",").map((column) => column.trim());
    if (columns.length < 3 || columns.length > 5) {
      throw new Error(`Row ${index + 1}: use UTR, amount, date, optional payer and detail.`);
    }
    const [utr, amount, txnDate, payerName = "", payerDetail = ""] = columns;
    if (!utr || !/^\d+(\.\d{1,2})?$/.test(amount)) {
      throw new Error(`Row ${index + 1}: enter a UTR and a positive amount in rupees.`);
    }
    const amountPaise = Math.round(Number(amount) * 100);
    if (!Number.isSafeInteger(amountPaise) || amountPaise <= 0) {
      throw new Error(`Row ${index + 1}: amount must be greater than zero.`);
    }
    if (!isValidDateOnly(txnDate)) {
      throw new Error(`Row ${index + 1}: date must use YYYY-MM-DD.`);
    }
    return {
      utr,
      amount_paise: amountPaise,
      txn_date: txnDate,
      payer_name: payerName || null,
      payer_detail: payerDetail || null,
    };
  });
}

function isValidDateOnly(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
