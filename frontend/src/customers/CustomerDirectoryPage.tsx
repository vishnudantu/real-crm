import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, AtSign, ChevronLeft, ChevronRight, Languages, LoaderCircle, Mail, Phone, Search, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { errorMessage } from "../shared/apiRequest";
import { customerKeys, fetchCustomer, fetchCustomers, searchCustomer } from "./customersApi";
import type { Contact, ContactSearchPayload, ContactSearchResponse } from "./customersModel";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, CustomerSkeleton, customerInputClass, formatCustomerDate } from "./CustomerUi";

function searchPayload(search: string): ContactSearchPayload | null {
  const value = search.trim();
  if (!value) return null;
  if (value.includes("@")) return { email: value };
  if (/^[+()\d\s-]{7,32}$/.test(value) && value.replace(/\D/g, "").length >= 7) return { phone: value };
  return null;
}

function ExactMatchCard({ result }: { result: ContactSearchResponse }) {
  if (result.exists && result.contact) {
    return (
      <section aria-label="Exact contact match" className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-semibold tracking-wider text-emerald-800 uppercase">Exact method match</p>
            <h2 className="mt-1 text-lg font-semibold text-charcoal">{result.contact.display_name}</h2>
            <p className="mt-1 text-sm text-charcoal/60">{result.matched_method?.kind.replaceAll("_", " ")} · {result.matched_method?.value}</p>
          </div>
          <Link to={`/admin/customers/${result.contact.id}`} className="inline-flex items-center gap-2 self-start rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory">Open contact <ArrowRight aria-hidden="true" className="size-4" /></Link>
        </div>
      </section>
    );
  }
  return (
    <section aria-label="No exact contact match" className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
      <h2 className="text-sm font-semibold text-charcoal">No contact matched this email or phone. Create a new contact?</h2>
      <p className="mt-2 text-xs leading-5 text-charcoal/65">Contacts are created when a website or channel lead is captured. Configure the website widget to start an enquiry; there is no separate contact-creation form or admin lead-creation route.</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link to="/admin/settings/widget" className="rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory">Open website widget settings</Link>
        <Link to="/admin/customers" className="rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal">Back to directory</Link>
      </div>
    </section>
  );
}

function DirectoryContactCard({ contact }: { contact: Contact }) {
  const detailQuery = useQuery({
    queryKey: customerKeys.detail(contact.id),
    queryFn: () => fetchCustomer(contact.id),
  });
  const methods = detailQuery.data?.contact.methods ?? [];
  const primaryMethod = methods.find((method) => method.is_primary) ?? methods[0];
  const MethodIcon = primaryMethod?.kind === "EMAIL" ? Mail : Phone;

  return (
    <Link to={`/admin/customers/${contact.id}`} className="group rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs transition hover:-translate-y-0.5 hover:border-charcoal/25 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-charcoal text-sm font-semibold text-ivory">{contact.display_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase()}</span>
        <span className={`rounded-full px-2.5 py-1 text-[0.65rem] font-semibold ${contact.status === "ACTIVE" ? "bg-emerald-50 text-emerald-800" : "bg-charcoal/5 text-charcoal/60"}`}>{contact.status}</span>
      </div>
      <h2 className="mt-4 truncate text-base font-semibold text-charcoal">{contact.display_name}</h2>
      <div className="mt-3 space-y-2 text-xs text-charcoal/55">
        {detailQuery.isLoading ? <p role="status" className="flex items-center gap-2"><LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />Loading contact summary…</p> : detailQuery.isError ? <p role="alert" className="text-xs leading-5 text-rose-700">Contact summary unavailable. Open the card to retry.{errorMessage(detailQuery.error, "Contact summary unavailable. Open the card to retry.")}</p> : <><p className="flex min-w-0 items-center gap-2"><MethodIcon aria-hidden="true" className="size-3.5 shrink-0" /><span className="truncate">{primaryMethod ? `${primaryMethod.is_primary ? "Primary" : primaryMethod.kind} · ${primaryMethod.value}` : "No primary contact method"}</span></p><p className="flex items-center gap-2"><Users aria-hidden="true" className="size-3.5" />{detailQuery.data?.opportunities.length ?? 0} {detailQuery.data?.opportunities.length === 1 ? "opportunity" : "opportunities"}</p></>}
        <p className="flex items-center gap-2"><Languages aria-hidden="true" className="size-3.5" />Language · <span className="font-medium text-charcoal uppercase">{contact.primary_language}</span></p>
        <p className="flex items-center gap-2"><AtSign aria-hidden="true" className="size-3.5" />Added {formatCustomerDate(contact.created_at)}</p>
      </div>
      <span className="mt-5 flex items-center justify-between border-t border-charcoal/10 pt-4 text-xs font-semibold text-charcoal">Open customer 360 <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1" /></span>
    </Link>
  );
}

export function CustomerDirectoryPage() {
  const [page, setPage] = useState(1);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [exactResult, setExactResult] = useState<ContactSearchResponse | null>(null);
  const [exactError, setExactError] = useState<unknown>(null);
  const [exactLoading, setExactLoading] = useState(false);
  const pageSize = 20;
  const query = useQuery({
    queryKey: customerKeys.list(page, pageSize, search),
    queryFn: () => fetchCustomers(page, pageSize, search),
  });

  const submitSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = searchDraft.trim();
    setPage(1);
    setSearch(normalized);
    setExactResult(null);
    setExactError(null);
    const payload = searchPayload(normalized);
    if (!payload) return;
    setExactLoading(true);
    try {
      setExactResult(await searchCustomer(payload));
    } catch (error: unknown) {
      setExactError(error);
    } finally {
      setExactLoading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <CustomerPageHeader eyebrow="Customer & opportunity graph" title="Customer directory" description="Find the canonical contact behind every conversation, opportunity and site visit." />
      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <form onSubmit={(event) => void submitSearch(event)} className="flex flex-col gap-3 sm:flex-row">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Search customers by name, email or phone</span>
            <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-charcoal/40" />
            <input type="search" maxLength={320} value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="Search name, email or phone…" className={`${customerInputClass} pl-10`} />
          </label>
          <button type="submit" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-charcoal px-5 py-2.5 text-xs font-semibold text-ivory hover:bg-charcoal/90"><Search aria-hidden="true" className="size-4" />Search directory</button>
        </form>
        <p className="mt-3 text-xs leading-5 text-charcoal/50">Name searches filter the directory. A complete email or phone also runs an exact, normalized identity check.</p>
      </section>
      {exactLoading && <CustomerSkeleton rows={1} />}
      <CustomerErrorBanner error={exactError} fallback="The exact contact lookup could not be completed." />
      {exactResult && <ExactMatchCard result={exactResult} />}
      {query.isLoading ? <CustomerSkeleton /> : query.isError ? (
        <CustomerErrorBanner error={query.error} fallback="The customer directory could not be loaded." onRetry={() => void query.refetch()} />
      ) : query.data && query.data.items.length === 0 ? (
        <CustomerEmptyState title={search ? "No matching customers" : "No customers yet"} description={search ? "Try a different name, or check an exact email or phone above." : "New leads will appear here once their contact identity is resolved."} action={<Link to="/admin/settings/widget" className="text-xs font-semibold text-charcoal underline">Configure website widget</Link>} />
      ) : query.data ? (
        <>
          <div className="flex items-center justify-between text-xs text-charcoal/55">
            <p>{query.data.total.toLocaleString()} {query.data.total === 1 ? "contact" : "contacts"}{search && <> matching <span className="font-semibold text-charcoal">“{search}”</span></>}</p>
            <p>Page {query.data.page} of {Math.max(query.data.pages, 1)}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {query.data.items.map((contact) => <DirectoryContactCard key={contact.id} contact={contact} />)}
          </div>
          {query.data.pages > 1 && (
            <nav aria-label="Customer directory pages" className="flex items-center justify-between rounded-2xl border border-charcoal/10 bg-white p-3">
              <button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))} className="inline-flex items-center gap-1.5 rounded-xl border border-charcoal/10 px-3.5 py-2 text-xs font-semibold disabled:opacity-40"><ChevronLeft aria-hidden="true" className="size-4" />Previous</button>
              <span className="text-xs text-charcoal/55">{page} / {query.data.pages}</span>
              <button type="button" disabled={page >= query.data.pages} onClick={() => setPage((current) => current + 1)} className="inline-flex items-center gap-1.5 rounded-xl border border-charcoal/10 px-3.5 py-2 text-xs font-semibold disabled:opacity-40">Next<ChevronRight aria-hidden="true" className="size-4" /></button>
            </nav>
          )}
        </>
      ) : null}
      <div className="flex items-center gap-2 text-xs text-charcoal/45"><Users aria-hidden="true" className="size-4" /><span>Canonical contacts exclude identities already merged into another customer.</span></div>
    </div>
  );
}
