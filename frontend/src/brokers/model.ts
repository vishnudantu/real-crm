export type BrokerStatus = "ACTIVE" | "INACTIVE" | "SUSPENDED";

export interface Broker {
  id: string;
  tenant_id: string;
  agency_name: string;
  contact_name: string;
  email: string | null;
  phone: string | null;
  rera_id: string | null;
  status: BrokerStatus;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrokerListResponse {
  items: Broker[];
  total: number;
}

export interface BrokerPerformance {
  broker_id: string;
  total_commission_paise: number;
  by_status: Record<string, number>;
  deal_count: number;
}

export interface BrokerCreateRequest {
  agency_name: string;
  contact_name: string;
  email: string | null;
  phone: string | null;
  rera_id: string | null;
  notes: string | null;
}

export function brokerStatusTone(status: string): string {
  if (status === "ACTIVE") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "SUSPENDED") return "border-rose-200 bg-rose-50 text-rose-700";
  return "border-charcoal/15 bg-charcoal/5 text-charcoal/60";
}

export function optionalText(value: string): string | null {
  return value.trim() || null;
}
