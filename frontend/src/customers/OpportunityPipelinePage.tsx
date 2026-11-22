import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, ChevronRight, KanbanSquare, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchProjects, fetchUsers } from "../admin/api";
import { customerKeys, fetchOpportunities } from "./customersApi";
import { groupOpportunitiesByStage } from "./customersModel";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader, CustomerSkeleton, formatCustomerDate, shortId } from "./CustomerUi";
import { OpportunityStageControl } from "./OpportunityStageControl";

export function OpportunityPipelinePage() {
  const [page, setPage] = useState(1);
  const pageSize = 100;
  const query = useQuery({ queryKey: customerKeys.opportunities(page, pageSize), queryFn: () => fetchOpportunities(page, pageSize) });
  const projectsQuery = useQuery({ queryKey: ["admin", "projects", "customer-reference"], queryFn: () => fetchProjects({ pageSize: 100 }) });
  const usersQuery = useQuery({ queryKey: ["admin", "users", "customer-reference"], queryFn: () => fetchUsers({ pageSize: 100 }) });
  const projectNames = new Map(projectsQuery.data?.items.map((project) => [project.id, project.name]) ?? []);
  const ownerNames = new Map(usersQuery.data?.items.map((user) => [user.id, user.full_name]) ?? []);
  const groups = groupOpportunitiesByStage(query.data?.items ?? []);

  return (
    <div className="mx-auto w-full max-w-[1800px] space-y-6">
      <CustomerPageHeader eyebrow="Customer & opportunity graph" title="Opportunity pipeline" description="Move purchase intent through the validated sales stages. Columns show the current API page, grouped by stage." action={<Link to="/admin/customers" className="inline-flex items-center gap-2 rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-xs font-semibold text-charcoal"><UserRound aria-hidden="true" className="size-4" />Customer directory</Link>} />
      <CustomerErrorBanner error={projectsQuery.isError ? projectsQuery.error : usersQuery.isError ? usersQuery.error : null} fallback="Project or owner names could not be loaded. IDs are shown instead." />
      {query.isLoading ? <CustomerSkeleton rows={4} /> : query.isError ? <CustomerErrorBanner error={query.error} fallback="The opportunity pipeline could not be loaded." onRetry={() => void query.refetch()} /> : query.data?.items.length === 0 ? <CustomerEmptyState title="No opportunities on this page" description="Opportunities are opened from qualified leads and connected to a project and canonical customer." action={<Link to="/admin/settings/widget" className="text-xs font-semibold underline">Set up lead capture</Link>} /> : query.data ? (
        <>
          <div className="flex items-center gap-2 text-xs text-charcoal/55"><KanbanSquare aria-hidden="true" className="size-4" /><span>{query.data.total.toLocaleString()} total opportunities · page {query.data.page} of {Math.max(query.data.pages, 1)}</span></div>
          <div className="overflow-x-auto pb-3">
            <div className="flex min-w-max items-start gap-4">
              {groups.map((group) => (
                <section key={group.stage} aria-label={`${group.label} opportunities`} className="w-72 shrink-0 rounded-2xl border border-charcoal/10 bg-charcoal/[0.035] p-3">
                  <header className="flex items-center justify-between px-1.5 py-2"><h2 className="text-xs font-semibold text-charcoal">{group.label}</h2><span className="grid min-w-6 place-items-center rounded-full bg-white px-1.5 py-0.5 text-[0.65rem] font-semibold text-charcoal/60">{group.items.length}</span></header>
                  <div className="mt-2 space-y-3">
                    {group.items.length === 0 ? <p className="rounded-xl border border-dashed border-charcoal/15 px-3 py-7 text-center text-xs text-charcoal/45">No opportunities</p> : group.items.map((opportunity) => (
                      <article key={opportunity.id} className="rounded-xl border border-charcoal/10 bg-white p-4 shadow-xs">
                        <Link to={`/admin/customers/${opportunity.contact_id}`} className="group flex items-start justify-between gap-3"><h3 className="min-w-0 text-sm font-semibold leading-5 text-charcoal">{projectNames.get(opportunity.project_id) ?? `Project ${shortId(opportunity.project_id)}`}</h3><ArrowUpRight aria-hidden="true" className="size-4 shrink-0 text-charcoal/40 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" /></Link>
                        <p className="mt-1.5 text-xs text-charcoal/55">{(opportunity.owner_user_id && ownerNames.get(opportunity.owner_user_id)) || (opportunity.owner_user_id ? `Owner ${shortId(opportunity.owner_user_id)}` : "Unassigned")}</p>
                        <dl className="mt-3 space-y-1.5 text-[0.68rem] text-charcoal/50"><div className="flex justify-between gap-3"><dt>Source</dt><dd className="text-right font-medium text-charcoal/70">{opportunity.source ?? "Not recorded"}</dd></div><div className="flex justify-between gap-3"><dt>Created</dt><dd className="font-medium text-charcoal/70">{formatCustomerDate(opportunity.created_at)}</dd></div>{opportunity.preferred_configuration && <div className="flex justify-between gap-3"><dt>Preference</dt><dd className="text-right font-medium text-charcoal/70">{opportunity.preferred_configuration}</dd></div>}</dl>
                        <div className="mt-4 border-t border-charcoal/10 pt-3"><OpportunityStageControl opportunity={opportunity} compact /></div>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
          {query.data.pages > 1 && <nav aria-label="Opportunity pages" className="flex items-center justify-between rounded-2xl border border-charcoal/10 bg-white p-3"><button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))} className="inline-flex items-center gap-1.5 rounded-xl border border-charcoal/10 px-3.5 py-2 text-xs font-semibold disabled:opacity-40"><ChevronLeft aria-hidden="true" className="size-4" />Previous</button><span className="text-xs text-charcoal/55">Page {page} of {query.data.pages}</span><button type="button" disabled={page >= query.data.pages} onClick={() => setPage((current) => current + 1)} className="inline-flex items-center gap-1.5 rounded-xl border border-charcoal/10 px-3.5 py-2 text-xs font-semibold disabled:opacity-40">Next<ChevronRight aria-hidden="true" className="size-4" /></button></nav>}
        </>
      ) : null}
    </div>
  );
}
