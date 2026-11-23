import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, LoaderCircle, Mail, Phone, Plus, Search } from "lucide-react";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader } from "../customers/CustomerUi";
import { saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { brokerKeys, fetchBrokers } from "./api";
import { brokerStatusTone } from "./model";
import type { Broker, BrokerStatus } from "./model";
import { AddBrokerDialog, BrokerDetail } from "./BrokerDialogs";

export function BrokersPage() {
  const [status, setStatus] = useState<BrokerStatus | "ALL">("ALL");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState<Broker | null>(null);
  const query = useQuery({ queryKey: brokerKeys.list(status, appliedSearch), queryFn: () => fetchBrokers(status, appliedSearch) });
  const brokers = query.data?.items ?? [];
  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Growth" title="Channel partners" description="Manage broker relationships, RERA details, partner status, and commission performance." action={<button type="button" className={salePrimaryButton} onClick={() => setAddOpen(true)}><Plus className="size-4" />Add partner</button>} />
    <section className="flex flex-col gap-3 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs sm:flex-row sm:items-end"><form className="relative flex-1" onSubmit={(event) => { event.preventDefault(); setAppliedSearch(search); }}><label htmlFor="broker-search" className="sr-only">Search partners</label><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-charcoal/35" /><input id="broker-search" type="search" maxLength={255} className={`${saleInputClasses} mt-0 pl-9`} placeholder="Search agency, contact, email or phone…" value={search} onChange={(event) => setSearch(event.target.value)} /></form><label className={saleLabelClasses}>Status<select className={`${saleInputClasses} sm:w-44`} value={status} onChange={(event) => setStatus(event.target.value as BrokerStatus | "ALL")}><option value="ALL">All statuses</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="SUSPENDED">Suspended</option></select></label><button type="button" className={saleSecondaryButton} onClick={() => setAppliedSearch(search)}>Search</button></section>
    <CustomerErrorBanner error={query.error} fallback="The channel partner directory could not be loaded." onRetry={() => void query.refetch()} />
    {query.isLoading && <div role="status" className="flex justify-center gap-2 rounded-2xl bg-white p-12 text-sm text-charcoal/60"><LoaderCircle className="size-5 animate-spin" />Loading channel partners…</div>}
    {!query.isLoading && !query.isError && !brokers.length && <CustomerEmptyState title="No channel partners found" description={appliedSearch || status !== "ALL" ? "Change your search or status filter." : "Add your first broker to track partner details and commission performance."} action={!appliedSearch && status === "ALL" && <button type="button" className={salePrimaryButton} onClick={() => setAddOpen(true)}><Plus className="size-4" />Add partner</button>} />}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{brokers.map((broker) => <article key={broker.id} className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex items-start justify-between gap-3"><span className="grid size-10 place-items-center rounded-xl bg-forest/10 text-forest"><BriefcaseBusiness className="size-5" /></span><span className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${brokerStatusTone(broker.status)}`}>{broker.status}</span></div><h2 className="mt-4 text-base font-semibold">{broker.agency_name}</h2><p className="mt-1 text-sm text-charcoal/65">{broker.contact_name}</p><div className="mt-4 space-y-2 text-xs text-charcoal/55">{broker.email && <p className="flex items-center gap-2 truncate"><Mail className="size-3.5 shrink-0" />{broker.email}</p>}{broker.phone && <p className="flex items-center gap-2"><Phone className="size-3.5" />{broker.phone}</p>}{broker.rera_id && <p className="text-[11px]">RERA {broker.rera_id}</p>}</div><button type="button" className={`${saleSecondaryButton} mt-5 w-full`} onClick={() => setSelected(broker)}>View partner & performance</button></article>)}</div>
    {query.data && <p className="text-xs text-charcoal/50">{query.data.total} partner{query.data.total === 1 ? "" : "s"}</p>}
    {addOpen && <AddBrokerDialog onClose={() => setAddOpen(false)} />}
    {selected && <BrokerDetail broker={selected} onClose={() => setSelected(null)} />}
  </div>;
}
