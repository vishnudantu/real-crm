import { useEffect, useState } from "react";
import { Compass, Sun } from "lucide-react";
import { SunPathStudio } from "./SunPathStudio";
import { useInventoryProjects } from "../inventory/useInventoryProjects";
import { useAdminUser } from "../admin/AdminAuthGuard";
import { inventoryInputClasses, inventoryLabelClasses } from "../inventory/inventoryUi";

/**
 * Standalone Sun & Facing studio under the Property sidebar group.
 * Pick a project, then explore the animated sun path, seasons, tower facing
 * dial, and the sun-score — the same engine as the unit/project drawer embeds.
 */
export function SunFacingPage() {
  const { projects, isLoading } = useInventoryProjects();
  const { user } = useAdminUser();
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);

  const project = projects.find((p) => p.id === projectId) ?? null;
  const isAdmin = user.role.name === "ADMIN" || user.role.name === "MANAGER";

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2 text-[0.65rem] font-semibold tracking-[0.18em] text-charcoal/50 uppercase">
            <Sun aria-hidden="true" className="size-3.5" />
            Property intelligence
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Sun & facing studio
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-charcoal/60">
            Explore the site's sun path across seasons, rotate tower facing on the compass,
            and see each unit's comfort score, Vastu note, and advisory pricing hint.
          </p>
        </div>
        <div className="min-w-56">
          <label htmlFor="solar-project" className={inventoryLabelClasses}>Project</label>
          <select
            id="solar-project"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            disabled={isLoading || projects.length === 0}
            className={inventoryInputClasses}
          >
            {projects.length === 0 && <option value="">No projects available</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {projectId && project ? (
        <SunPathStudio
          projectId={projectId}
          projectName={project.name}
          isAdmin={isAdmin}
        />
      ) : (
        <div className="flex min-h-64 flex-col items-center justify-center gap-2 rounded-2xl border border-charcoal/10 bg-white p-8 text-center">
          <Compass aria-hidden="true" className="size-8 text-charcoal/25" />
          <p className="text-sm font-semibold text-charcoal">Select a project to begin</p>
          <p className="max-w-md text-xs leading-relaxed text-charcoal/55">
            {isLoading ? "Loading projects…" : "Choose a project above to load its sun path and facing studio."}
          </p>
        </div>
      )}
    </div>
  );
}
