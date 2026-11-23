import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarClock, CheckCircle2, LoaderCircle, Plus } from "lucide-react";
import { fetchProjects } from "../admin/api";
import { CustomerEmptyState, CustomerErrorBanner, CustomerPageHeader } from "../customers/CustomerUi";
import { formatShortDate, saleInputClasses, saleLabelClasses, salePrimaryButton, saleSecondaryButton } from "../admin/sales/salesBookingUi";
import { constructionKeys, fetchMilestones, fetchProgress } from "./api";
import { milestoneStatusLabel, milestoneStatusTone, nextSequence } from "./model";
import type { ConstructionMilestone } from "./model";
import { CertifyDialog, CreateMilestoneDialog, ProgressDialog } from "./ConstructionDialogs";

export function ConstructionPage() {
  const [projectId, setProjectId] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [progressTarget, setProgressTarget] = useState<ConstructionMilestone | null>(null);
  const [certifyTarget, setCertifyTarget] = useState<ConstructionMilestone | null>(null);
  const projects = useQuery({ queryKey: ["admin", "projects", "construction-selector"], queryFn: () => fetchProjects({ page: 1, pageSize: 100 }) });
  useEffect(() => { if (!projectId && projects.data?.items[0]) setProjectId(projects.data.items[0].id); }, [projectId, projects.data]);
  const milestones = useQuery({ queryKey: constructionKeys.milestones(projectId), queryFn: () => fetchMilestones(projectId), enabled: Boolean(projectId) });
  const progress = useQuery({ queryKey: constructionKeys.progress(projectId), queryFn: () => fetchProgress(projectId), enabled: Boolean(projectId) });
  const items = milestones.data ?? [];
  const project = projects.data?.items.find((item) => item.id === projectId);
  return <div className="space-y-6">
    <CustomerPageHeader eyebrow="Operations" title="Construction progress" description="Track each project's milestone sequence, site observations, completion, and certified evidence." action={projectId && <button type="button" className={salePrimaryButton} onClick={() => setCreateOpen(true)}><Plus className="size-4" />Add milestone</button>} />
    <section className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs"><label className={`${saleLabelClasses} block max-w-md`}>Project<select className={saleInputClasses} value={projectId} onChange={(event) => setProjectId(event.target.value)} disabled={projects.isLoading || projects.isError}><option value="">{projects.isLoading ? "Loading projects…" : "Select a project"}</option>{projects.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.location}</option>)}</select></label><CustomerErrorBanner error={projects.error} fallback="Projects could not be loaded." onRetry={() => void projects.refetch()} /></section>
    {project && progress.data && <section className="grid gap-3 sm:grid-cols-3"><Metric label="Overall completion" value={`${Math.round(progress.data.avg_percent)}%`} /><Metric label="Milestones" value={String(progress.data.total)} /><Metric label="Delayed" value={String(progress.data.delayed_count)} alert={progress.data.delayed_count > 0} /></section>}
    <CustomerErrorBanner error={milestones.error ?? progress.error} fallback="Construction progress could not be loaded." onRetry={() => { void milestones.refetch(); void progress.refetch(); }} />
    {(milestones.isLoading || progress.isLoading) && <div role="status" className="flex justify-center gap-2 rounded-2xl bg-white p-12 text-sm text-charcoal/60"><LoaderCircle className="size-5 animate-spin" />Loading project timeline…</div>}
    {projectId && !milestones.isLoading && !milestones.isError && items.length === 0 && <CustomerEmptyState title="No milestones for this project" description="Create the first planned milestone to start the construction timeline." action={<button type="button" className={salePrimaryButton} onClick={() => setCreateOpen(true)}><Plus className="size-4" />Add milestone</button>} />}
    {items.length > 0 && <section aria-label={`${project?.name ?? "Project"} milestone timeline`} className="relative space-y-4 before:absolute before:bottom-6 before:left-6 before:top-6 before:w-px before:bg-charcoal/15 sm:before:left-8">{items.map((milestone) => <article key={milestone.id} className="relative ml-12 rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs sm:ml-16"><span className={`absolute -left-12 top-5 grid size-7 place-items-center rounded-full border-4 border-[#FAFAF7] text-[10px] font-bold sm:-left-16 sm:ml-2 ${milestone.status === "CERTIFIED" ? "bg-forest text-white" : "bg-charcoal/10 text-charcoal"}`}>{milestone.status === "CERTIFIED" ? <CheckCircle2 className="size-4" /> : milestone.sequence_no}</span><div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">{milestone.name}</h2><span className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${milestoneStatusTone(milestone.status)}`}>{milestoneStatusLabel(milestone.status)}</span></div><p className="mt-2 flex items-center gap-1.5 text-xs text-charcoal/55"><CalendarClock className="size-3.5" />Planned {formatShortDate(milestone.planned_date)}{milestone.actual_date && ` · Completed ${formatShortDate(milestone.actual_date)}`}</p><div className="mt-4 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-charcoal/10"><div className="h-full rounded-full bg-forest transition-all" style={{ width: `${milestone.percent_complete}%` }} /></div><span className="w-10 text-right text-xs font-semibold">{milestone.percent_complete}%</span></div>{milestone.evidence_notes && <p className="mt-4 rounded-xl bg-forest/5 p-3 text-xs leading-5 text-charcoal/65"><strong>Evidence: </strong>{milestone.evidence_notes}</p>}</div><div className="flex shrink-0 flex-wrap gap-2">{milestone.status !== "CERTIFIED" && <button type="button" className={saleSecondaryButton} onClick={() => setProgressTarget(milestone)}>Update progress</button>}{milestone.status === "COMPLETED" && <button type="button" className={salePrimaryButton} onClick={() => setCertifyTarget(milestone)}><CheckCircle2 className="size-4" />Certify</button>}</div></div></article>)}</section>}
    {!projectId && !projects.isLoading && !projects.isError && <CustomerEmptyState title="Select a project" description="Choose a project to view and manage its construction milestone timeline." />}
    {createOpen && projectId && <CreateMilestoneDialog projectId={projectId} sequence={nextSequence(items)} onClose={() => setCreateOpen(false)} />}
    {progressTarget && <ProgressDialog milestone={progressTarget} onClose={() => setProgressTarget(null)} />}
    {certifyTarget && <CertifyDialog milestone={certifyTarget} onClose={() => setCertifyTarget(null)} />}
  </div>;
}

function Metric({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return <div className="rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs"><div className="flex items-center justify-between"><p className="text-xs text-charcoal/55">{label}</p><Building2 className={`size-4 ${alert ? "text-rose-500" : "text-forest"}`} /></div><p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p></div>;
}
