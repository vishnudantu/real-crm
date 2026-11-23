import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, AtSign, ChevronLeft, ChevronRight, Languages, LoaderCircle, Mail, Pencil, Phone, Plus, Search, UserPlus, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { customerKeys, fetchCustomer, fetchCustomers, searchCustomer } from "./customersApi";
import type { Contact, ContactSearchPayload, ContactSearchResponse } from "./customersModel";
import { ContactFormModal } from "./ContactFormModal";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, CustomerSkeleton, customerInputClass, formatCustomerDate } from "./CustomerUi";

function searchPayload(search: string): ContactSearchPayload | null {
  const value = search.trim();
  if (!value) return null;
  if (value.includes("@")) return { email: value };
  if (/^[+()\d\s-]{7,32}$/.test(value) && value.replace(/\D/g, "").length >= 7) return { phone: value };
  return null;
}

function ExactMatchCard({ result, onCreateContact }: {
  result: ContactSearchResponse;
  onCreateContact: () => void;
}) {
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
      <h2 className="text-sm font-semibold text-charcoal">No contact matched this email or phone. Create a new customer?</h2>
      <p className="mt-2 text-xs leading-5 text-charcoal/65">Contacts are also created automatically when a website or channel lead is captured. Creating here is idempotent: a repeat submission returns the existing customer rather than a duplicate.</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onCreateContact} className="inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory"><UserPlus aria-hidden="true" className="size-4" />Create this contact</button>
        <Link to="/admin/settings/widget" className="rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal">Website widget settings</Link>
      </div>
    </section>
  );
}

function DirectoryContactCard({ contact, onEdit }: { contact: Contact; onEdit: (contact: Contact) => void }) {
  const detailQuery = useQuery({
    queryKey: customerKeys.detail(contact.id),
    queryFn: () => fetchCustomer(contact.id),
  });
  const methods = detailQuery.data?.contact.methods ?? [];
  const primaryMethod = methods.find((method) => method.is_primary) ?? methods[0];
  const MethodIcon = primaryMethod?.kind === "EMAIL" ? Mail : Phone;

  return (
    <article className="flex flex-col rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs transition hover:border-charcoal/25 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-charcoal text-sm font-semibold text-ivory">{contact.display_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase()}</span>
        <span className={`rounded-full px-2.5 py-1 text-[0.65rem] font-semibold ${contact.status === "ACTIVE" ? "bg-emerald-50 text-emerald-800" : "bg-charcoal/5 text-charcoal/60"}`}>{contact.status}</span>
      </div>
      <h2 className="mt-4 truncate text-base font-semibold text-charcoal">
        <Link to={`/admin/customers/${contact.id}`} className="hover:underline">{contact.display_name}</Link>
      </h2>
      <div className="mt-3 flex-1 space-y-2 text-xs text-charcoal/55">
        {detailQuery.isLoading ? <p role="status" className="flex items-center gap-2"><LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />Loading contact summary…</p> : detailQuery.isError ? <p role="alert" className="text-xs leading-5 text-rose-700">Contact summary unavailable. Open the card to retry.</p> : <><p className="flex min-w-0 items-center gap-2"><MethodIcon aria-hidden="true" className="size-3.5 shrink-0" /><span className="truncate">{primaryMethod ? `${primaryMethod.is_primary ? "Primary" : primaryMethod.kind} · ${primaryMethod.value}` : "No primary contact method"}</span></p><p className="flex items-center gap-2"><Users aria-hidden="true" className="size-3.5" />{detailQuery.data?.opportunities.length ?? 0} {detailQuery.data?.opportunities.length === 1 ? "opportunity" : "opportunities"}</p></>}
        <p className="flex items-center gap-2"><Languages aria-hidden="true" className="size-3.5" />Language · <span className="font-medium text-charcoal uppercase">{contact.primary_language}</span></p>
        <p className="flex items-center gap-2"><AtSign aria-hidden="true" className="size-3.5" />Added {formatCustomerDate(contact.created_at)}</p>
      </div>
      <div className="mt-5 flex items-center justify-between gap-2 border-t border-charcoal/10 pt-4">
        <Link to={`/admin/customers/${contact.id}`} className="inline-flex items-center gap-1.5 text-xs font-semibold text-charcoal hover:underline">Open customer 360 <ArrowRight aria-hidden="true" className="size-4" /></Link>
        <button type="button" onClick={() => onEdit(contact)} aria-label={`Edit ${contact.display_name}`} className="inline-flex items-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3 py-1.5 text-[11px] font-semibold text-charcoal/75 transition-colors hover:bg-charcoal/5 hover:text-charcoal">
          <Pencil aria-hidden="true" className="size-3.5" />Edit
        </button>
      </div>
    </article>
  );
}

export function CustomerDirectoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [exactResult, setExactResult] = useState<ContactSearchResponse | null>(null);
  const [exactError, setExactError] = useState<unknown>(null);
  const [exactLoading, setExactLoading] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addDefaults, setAddDefaults] = useState<{ email: string; phone: string } | null>(null);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const pageSize = 20;
  const query = useQuery({
    queryKey: customerKeys.list(page, pageSize, search),
    queryFn: () => fetchCustomers(page, pageSize, search),
  });

  const openAddWithIdentity = () => {
    const value = searchDraft.trim();
    const payload = searchPayload(value);
    setAddDefaults(payload ? { email: payload.email ?? "", phone: payload.phone ?? "" } : null);
    setAddOpen(true);
  };

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
      <CustomerPageHeader
        eyebrow="Customer & opportunity graph"
        title="Customer directory"
        description="Find the canonical contact behind every conversation, opportunity and site visit."
        action={
          <button type="button" onClick={() => { setAddDefaults(null); setAddOpen(true); }} className="inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory hover:opacity-95">
            <Plus aria-hidden="true" className="size-4" />Add customer
          </button>
        }
      />
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
      {exactResult && <ExactMatchCard result={exactResult} onCreateContact={openAddWithIdentity} />}
      {query.isLoading ? <CustomerSkeleton /> : query.isError ? (
        <CustomerErrorBanner error={query.error} fallback="The customer directory could not be loaded." onRetry={() => void query.refetch()} />
      ) : query.data && query.data.items.length === 0 ? (
        <CustomerEmptyState
          title={search ? "No matching customers" : "No customers yet"}
          description={search ? "Try a different name, or check an exact email or phone above." : "Add a customer manually, or connect the website widget to capture enquiries automatically."}
          action={
            <div className="flex flex-wrap justify-center gap-3">
              <button type="button" onClick={() => { setAddDefaults(null); setAddOpen(true); }} className="inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory hover:opacity-95"><UserPlus aria-hidden="true" className="size-4" />Add customer</button>
              <Link to="/admin/settings/widget" className="inline-flex items-center rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal">Configure website widget</Link>
            </div>
          }
        />
      ) : query.data ? (
        <>
          <div className="flex items-center justify-between text-xs text-charcoal/55">
            <p>{query.data.total.toLocaleString()} {query.data.total === 1 ? "contact" : "contacts"}{search && <> matching <span className="font-semibold text-charcoal">“{search}”</span></>}</p>
            <p>Page {query.data.page} of {Math.max(query.data.pages, 1)}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {query.data.items.map((contact) => <DirectoryContactCard key={contact.id} contact={contact} onEdit={setEditingContact} />)}
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
      {addOpen && (
        <ContactFormModal
          mode="create"
          initialValues={addDefaults ?? undefined}
          onClose={() => setAddOpen(false)}
          onCreated={(contact, created) => {
            if (created) navigate(`/admin/customers/${contact.id}`);
          }}
        />
      )}
      {editingContact && (
        <ContactFormModal
          mode="edit"
          contact={editingContact}
          onClose={() => setEditingContact(null)}
          onSaved={(contact) => navigate(`/admin/customers/${contact.id}`)}
        />
      )}
    </div>
  );
}
