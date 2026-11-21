import { RotateCcw, Search } from "lucide-react";
import type { ProjectItem } from "../projectModel";
import type { SaleStatus } from "./salesBookingModel";
import { SALE_STATUSES } from "./salesBookingModel";
import { saleInputClasses, saleLabelClasses, saleSecondaryButton } from "./salesBookingUi";

interface SalesBookingFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  status: SaleStatus | "ALL";
  onStatusChange: (value: SaleStatus | "ALL") => void;
  projectId: string;
  onProjectChange: (value: string) => void;
  projects: ProjectItem[];
  onReset: () => void;
}

export function SalesBookingFilters({
  search,
  onSearchChange,
  status,
  onStatusChange,
  projectId,
  onProjectChange,
  projects,
  onReset,
}: SalesBookingFiltersProps) {
  const hasFilters =
    search.trim() !== "" || status !== "ALL" || projectId !== "ALL";

  return (
    <div className="rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="md:col-span-2">
          <label htmlFor="sale-search" className={saleLabelClasses}>
            Search
          </label>
          <div className="relative mt-1.5">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-charcoal/40"
            />
            <input
              id="sale-search"
              type="search"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search by unit, lead name, phone, or project…"
              className={`${saleInputClasses} mt-0 pl-9`}
            />
          </div>
        </div>

        <div>
          <label htmlFor="sale-status" className={saleLabelClasses}>
            Status
          </label>
          <select
            id="sale-status"
            value={status}
            onChange={(event) =>
              onStatusChange(event.target.value as SaleStatus | "ALL")
            }
            className={saleInputClasses}
          >
            <option value="ALL">All statuses</option>
            {SALE_STATUSES.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="sale-project" className={saleLabelClasses}>
            Project
          </label>
          <select
            id="sale-project"
            value={projectId}
            onChange={(event) => onProjectChange(event.target.value)}
            className={saleInputClasses}
          >
            <option value="ALL">All projects</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {hasFilters && (
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={onReset}
            className={saleSecondaryButton}
            aria-label="Reset filters"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            <span>Clear filters</span>
          </button>
        </div>
      )}
    </div>
  );
}
