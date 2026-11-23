import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowLeft, ArrowRight, CalendarDays, CheckCircle2, CircleDollarSign, Clock3, Languages, Mail, MessageCircle, Pencil, Phone, Receipt, ShieldCheck, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { fetchProjects, fetchUsers } from "../admin/api";
import { customerKeys, fetchCustomer } from "./customersApi";
import { groupTimelineByDay, stageLabel } from "./customersModel";
import type { TimelineItem } from "./customersModel";
import { ContactFormModal } from "./ContactFormModal";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, CustomerSkeleton, formatCustomerDate, shortId } from "./CustomerUi";
import { OpportunityStageControl } from "./OpportunityStageControl";

const TIMELINE_ICONS: Readonly<Record<string, LucideIcon>> = {
  lead: UserRound,
  conversation: MessageCircle,
  message: MessageCircle,
  channel_conversation: MessageCircle,
  channel_message: MessageCircle,
  booking: CalendarDays,
  call: Phone,
  sale_booking: CircleDollarSign,
  receipt: Receipt,
};

function provenanceSource(provenance: Readonly<Record<string, unknown>>): string {
  return typeof provenance.source === "string" ? provenance.source : "Not recorded";
}

function TimelineEvent({ item }: { item: TimelineItem }) {
  const Icon = TIMELINE_ICONS[item.type] ?? Activity;
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      <span className="relative z-10 grid size-9 shrink-0 place-items-center rounded-xl border border-charcoal/10 bg-white text-charcoal/65"><Icon aria-hidden="true" className="size-4" /></span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-start">
          <p className="text-sm leading-6 text-charcoal">{item.summary}</p>
          <time dateTime={item.occurred_at} className="shrink-0 text-[0.68rem] whitespace-nowrap text-charcoal/45">{formatCustomerDate(item.occurred_at, true)}</time>
        </div>
        <p className="mt-1 text-[0.68rem] text-charcoal/45"><span className="font-medium text-charcoal/60">{item.type.replaceAll("_", " ")}</span>{item.actor && <> · {item.actor}</>}</p>
      </div>
    </li>
  );
}

export function Customer360Page() {
  const { id = "" } = useParams<{ id: string }>();
  const [editOpen, setEditOpen] = useState(false);
  const query = useQuery({ queryKey: customerKeys.detail(id), queryFn: () => fetchCustomer(id), enabled: Boolean(id) });
  const projectsQuery = useQuery({ queryKey: ["admin", "projects", "customer-reference"], queryFn: () => fetchProjects({ pageSize: 100 }) });
  const usersQuery = useQuery({ queryKey: ["admin", "users", "customer-reference"], queryFn: () => fetchUsers({ pageSize: 100 }) });
  const projectNames = new Map(projectsQuery.data?.items.map((project) => [project.id, project.name]) ?? []);
  const ownerNames = new Map(usersQuery.data?.items.map((user) => [user.id, user.full_name]) ?? []);

  if (query.isLoading) return <div className="mx-auto max-w-7xl space-y-5"><CustomerPageHeader eyebrow="Customer 360" title="Loading customer…" description="Bringing together contact identity, opportunities and activity." /><CustomerSkeleton rows={6} /></div>;
  if (query.isError || !query.data) return <div className="mx-auto max-w-7xl space-y-5"><Link to="/admin/customers" className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal"><ArrowLeft aria-hidden="true" className="size-4" />Customer directory</Link><CustomerErrorBanner error={query.error} fallback="This customer 360 view could not be loaded." onRetry={() => void query.refetch()} /></div>;

  const { contact, opportunities, timeline, freshness } = query.data;
  const timelineGroups = groupTimelineByDay(timeline);
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <Link to="/admin/customers" className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal/65 hover:text-charcoal"><ArrowLeft aria-hidden="true" className="size-4" />Customer directory</Link>
      <CustomerPageHeader eyebrow="Customer & opportunity graph" title={contact.display_name} description={`Canonical contact · ${contact.canonical_key}`} action={
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setEditOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal hover:bg-charcoal/5">
            <Pencil aria-hidden="true" className="size-3.5" />Edit customer
          </button>
          <Link to={`/admin/customers/${contact.id}/duplicates`} className="inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-xs font-semibold text-ivory">Review duplicates<ArrowRight aria-hidden="true" className="size-4" /></Link>
        </div>
      } />
      <CustomerErrorBanner error={projectsQuery.isError ? projectsQuery.error : usersQuery.isError ? usersQuery.error : null} fallback="Project or owner names could not be loaded. IDs are shown instead." />
      <section className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs">
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex items-center gap-4"><span className="grid size-16 shrink-0 place-items-center rounded-2xl bg-charcoal text-xl font-semibold text-ivory">{contact.display_name.slice(0, 2).toUpperCase()}</span><div><h2 className="text-xl font-semibold">{contact.display_name}</h2><p className="mt-1 text-xs text-charcoal/50">Customer since {formatCustomerDate(contact.created_at)}</p></div></div>
          <div className="flex flex-wrap gap-2"><span className="inline-flex items-center gap-1.5 rounded-full bg-charcoal/5 px-3 py-1.5 text-xs font-semibold"><Languages aria-hidden="true" className="size-3.5" />{contact.primary_language.toUpperCase()}</span><span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800"><CheckCircle2 aria-hidden="true" className="size-3.5" />{contact.status}</span></div>
        </div>
        <dl className="grid gap-px border-t border-charcoal/10 bg-charcoal/10 sm:grid-cols-3">
          <div className="bg-[#FAFAF7] p-4"><dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">Contact methods</dt><dd className="mt-1 text-lg font-semibold">{contact.methods.length}</dd></div>
          <div className="bg-[#FAFAF7] p-4"><dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">Opportunities</dt><dd className="mt-1 text-lg font-semibold">{opportunities.length}</dd></div>
          <div className="bg-[#FAFAF7] p-4"><dt className="text-[0.65rem] font-semibold tracking-wider text-charcoal/45 uppercase">Last profile update</dt><dd className="mt-1 text-sm font-semibold">{formatCustomerDate(contact.updated_at)}</dd></div>
        </dl>
      </section>
      {contact.notes && <section className="rounded-2xl border border-charcoal/10 bg-white p-5"><h2 className="text-sm font-semibold">Contact notes</h2><p className="mt-2 text-sm leading-6 whitespace-pre-wrap text-charcoal/65">{contact.notes}</p></section>}

      <section className="overflow-hidden rounded-2xl border border-charcoal/10 bg-white shadow-xs">
        <div className="border-b border-charcoal/10 p-5 sm:p-6"><h2 className="flex items-center gap-2 text-base font-semibold"><Mail aria-hidden="true" className="size-4" />Contact methods</h2><p className="mt-1 text-xs text-charcoal/55">Normalized identity methods with verification and provenance.</p></div>
        {contact.methods.length === 0 ? <div className="p-5"><CustomerEmptyState title="No contact methods" description="No email, phone or channel identity has been attached to this contact." /></div> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-charcoal/5 text-[0.65rem] tracking-wider text-charcoal/50 uppercase"><tr><th className="px-5 py-3 font-semibold">Kind</th><th className="px-5 py-3 font-semibold">Value</th><th className="px-5 py-3 font-semibold">Verified</th><th className="px-5 py-3 font-semibold">Primary</th><th className="px-5 py-3 font-semibold">Provenance source</th><th className="px-5 py-3 font-semibold">Last seen</th></tr></thead><tbody className="divide-y divide-charcoal/10">{contact.methods.map((method) => <tr key={method.id}><td className="px-5 py-4 font-medium">{method.kind.replaceAll("_", " ")}</td><td className="max-w-64 px-5 py-4 break-all font-medium">{method.value}</td><td className="px-5 py-4"><span className={method.verification_state === "VERIFIED" ? "text-emerald-700" : "text-charcoal/55"}>{method.verification_state}</span></td><td className="px-5 py-4">{method.is_primary ? <ShieldCheck aria-label="Primary method" className="size-4 text-emerald-700" /> : "—"}</td><td className="px-5 py-4 text-charcoal/60">{provenanceSource(method.provenance)}</td><td className="px-5 py-4 text-charcoal/60">{method.last_seen_at ? formatCustomerDate(method.last_seen_at) : "Not recorded"}</td></tr>)}</tbody></table></div>
        )}
      </section>

      <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
        <div className="flex items-center justify-between border-b border-charcoal/10 pb-5"><div><h2 className="text-base font-semibold">Opportunities</h2><p className="mt-1 text-xs text-charcoal/55">Project intent, ownership and validated stage transitions.</p></div><Link to="/admin/opportunities" className="text-xs font-semibold hover:underline">Full pipeline</Link></div>
        {opportunities.length === 0 ? <div className="mt-5"><CustomerEmptyState title="No opportunities yet" description="An opportunity is opened when this customer’s lead is connected to a project." action={<Link to="/admin/settings/widget" className="text-xs font-semibold underline">Set up lead capture</Link>} /></div> : <div className="mt-5 space-y-4">{opportunities.map((opportunity) => <article key={opportunity.id} className="rounded-xl border border-charcoal/10 bg-[#FAFAF7] p-4"><div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]"><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{projectNames.get(opportunity.project_id) ?? `Project ${shortId(opportunity.project_id)}`}</h3><span className="rounded-full bg-charcoal/5 px-2.5 py-1 text-[0.65rem] font-semibold">{stageLabel(opportunity.stage)}</span></div><dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3"><div><dt className="text-charcoal/45">Owner</dt><dd className="mt-1 font-medium">{(opportunity.owner_user_id && ownerNames.get(opportunity.owner_user_id)) || (opportunity.owner_user_id ? shortId(opportunity.owner_user_id) : "Unassigned")}</dd></div><div><dt className="text-charcoal/45">Source</dt><dd className="mt-1 font-medium">{opportunity.source ?? "Not recorded"}</dd></div><div><dt className="text-charcoal/45">Created</dt><dd className="mt-1 font-medium">{formatCustomerDate(opportunity.created_at)}</dd></div></dl>{opportunity.preferred_configuration && <p className="mt-3 text-xs text-charcoal/55">Preference · {opportunity.preferred_configuration}</p>}</div><OpportunityStageControl opportunity={opportunity} compact /></div></article>)}</div>}
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:p-6">
          <div className="border-b border-charcoal/10 pb-5"><h2 className="flex items-center gap-2 text-base font-semibold"><Clock3 aria-hidden="true" className="size-4" />Universal timeline</h2><p className="mt-1 text-xs text-charcoal/55">Latest activity first, grouped by UTC day. Up to 200 events.</p></div>
          {timelineGroups.length === 0 ? <div className="mt-5"><CustomerEmptyState title="No activity yet" description="Leads, messages, calls, visits and sale events will form a unified timeline here." /></div> : <div className="mt-6 space-y-7">{timelineGroups.map((group) => <section key={group.dayKey} aria-label={group.label}><h3 className="mb-4 text-xs font-semibold tracking-wider text-charcoal/50 uppercase">{group.label}</h3><ul className="relative before:absolute before:top-4 before:bottom-4 before:left-[17px] before:w-px before:bg-charcoal/10">{group.items.map((item, index) => <TimelineEvent key={`${item.occurred_at}-${item.type}-${index}`} item={item} />)}</ul></section>)}</div>}
        </section>
        <aside className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs lg:sticky lg:top-28"><h2 className="text-sm font-semibold">Data freshness</h2><p className="mt-1 text-xs leading-5 text-charcoal/50">Most recent source event returned by the graph.</p><dl className="mt-4 divide-y divide-charcoal/10">{Object.entries(freshness).map(([source, timestamp]) => <div key={source} className="py-3"><dt className="text-xs font-medium capitalize text-charcoal/60">{source}</dt><dd className="mt-1 text-xs font-semibold text-charcoal">{timestamp ? formatCustomerDate(timestamp, true) : "No events"}</dd></div>)}</dl></aside>
      </div>
      {editOpen && (
        <ContactFormModal
          mode="edit"
          contact={contact}
          onClose={() => setEditOpen(false)}
          onSaved={() => void query.refetch()}
        />
      )}
    </div>
  );
}
