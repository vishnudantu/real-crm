import { useEffect, useRef, useState } from "react";
import { LoaderCircle, X } from "lucide-react";
import { StaffPicker } from "./StaffPicker";
import type { TeamStaffUser } from "./teamchatModel";

interface NewChannelDialogProps {
  members: readonly TeamStaffUser[];
  membersLoading: boolean;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onCreate: (payload: { name: string; topic: string | null; member_ids: string[] }) => void;
}

export function NewChannelDialog({
  members, membersLoading, pending, error, onClose, onCreate,
}: NewChannelDialogProps) {
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.querySelector<HTMLInputElement>("input")?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-charcoal/45 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-channel-title"
        className="max-h-[90svh] w-full max-w-lg overflow-y-auto rounded-2xl border border-charcoal/10 bg-ivory p-5 shadow-2xl"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 id="new-channel-title" className="text-lg font-semibold text-charcoal">New channel</h2>
            <p className="mt-1 text-sm text-charcoal/60">Start a focused conversation with your staff.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close new channel dialog" className="rounded-lg p-1.5 text-charcoal/60 hover:bg-charcoal/5">
            <X aria-hidden="true" className="size-5" />
          </button>
        </div>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) onCreate({ name: name.trim(), topic: topic.trim() || null, member_ids: selectedIds });
        }}>
          <div className="space-y-4">
            <label className="block text-xs font-semibold text-charcoal/70">
              Channel name
              <input
                required
                maxLength={80}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. leasing-team"
                className="mt-1.5 w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-sm font-normal outline-none focus:border-forest"
              />
            </label>
            <label className="block text-xs font-semibold text-charcoal/70">
              Topic <span className="font-normal text-charcoal/45">(optional)</span>
              <input
                maxLength={500}
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="What is this channel for?"
                className="mt-1.5 w-full rounded-xl border border-charcoal/15 bg-white px-3 py-2.5 text-sm font-normal outline-none focus:border-forest"
              />
            </label>
            <div>
              <p className="mb-1.5 text-xs font-semibold text-charcoal/70">Add staff members</p>
              <StaffPicker
                members={members}
                loading={membersLoading}
                selectedIds={selectedIds}
                onToggle={(id) => setSelectedIds((current) =>
                  current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
                )}
              />
            </div>
          </div>
          {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-xl px-4 py-2.5 text-sm font-semibold text-charcoal/65 hover:bg-charcoal/5">Cancel</button>
            <button type="submit" disabled={!name.trim() || pending} className="inline-flex items-center gap-2 rounded-xl bg-charcoal px-4 py-2.5 text-sm font-semibold text-ivory disabled:opacity-45">
              {pending && <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />}
              Create channel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
