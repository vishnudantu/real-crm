import { useMemo, useState } from "react";
import { AtSign, Check, UserPlus } from "lucide-react";
import { filterMembersByName } from "./teamchatModel";
import type { TeamStaffUser } from "./teamchatModel";

interface StaffPickerProps {
  members: readonly TeamStaffUser[];
  selectedIds: readonly string[];
  onToggle: (id: string) => void;
  loading?: boolean;
}

export function StaffPicker({ members, selectedIds, onToggle, loading = false }: StaffPickerProps) {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => filterMembersByName(members, search), [members, search]);
  return (
    <div className="overflow-hidden rounded-xl border border-charcoal/15 bg-white">
      <label className="flex items-center gap-2 border-b border-charcoal/10 px-3 py-2.5">
        <AtSign aria-hidden="true" className="size-4 text-charcoal/45" />
        <span className="sr-only">Search staff members</span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Mention or add a teammate…"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-charcoal/45"
        />
      </label>
      <div className="max-h-56 overflow-y-auto p-1.5">
        {loading && <p className="px-3 py-4 text-center text-xs text-charcoal/55">Loading teammates…</p>}
        {!loading && filtered.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-charcoal/55">No staff members match.</p>
        )}
        {filtered.map((person) => {
          const selected = selectedIds.includes(person.id);
          return (
            <button
              key={person.id}
              type="button"
              aria-pressed={selected}
              onClick={() => onToggle(person.id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                selected ? "bg-forest/10 text-forest" : "text-charcoal hover:bg-charcoal/5"
              }`}
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-charcoal/10 text-[0.65rem] font-bold">
                {person.full_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{person.full_name}</span>
                <span className="block truncate text-xs text-charcoal/55">{person.email}</span>
              </span>
              {selected ? <Check aria-hidden="true" className="size-4" /> : <UserPlus aria-hidden="true" className="size-4 text-charcoal/40" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
