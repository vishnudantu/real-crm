import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BadgeCheck,
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  Lock,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { ApiError } from "../../auth/api";
import { errorMessage } from "../../shared/apiRequest";
import {
  createCustomRole,
  deleteCustomRole,
  fetchCustomRoles,
  fetchPermissionRegistry,
  updateCustomRole,
} from "./roleApi";
import type { CustomRoleItem } from "./roleDesignerModel";
import {
  MAX_CUSTOM_ROLE_PERMISSIONS,
  areaLabel,
  groupPermissions,
  summarizePermissions,
  togglePermission,
  validateRoleDraft,
} from "./roleDesignerModel";

interface RoleDraft {
  id: string | null;
  name: string;
  description: string;
  permissions: string[];
}

const BLANK_DRAFT: RoleDraft = { id: null, name: "", description: "", permissions: [] };

function draftFromRole(role: CustomRoleItem): RoleDraft {
  return {
    id: role.id,
    name: role.name,
    description: role.description ?? "",
    permissions: [...role.permissions],
  };
}

export function RolesSettingsTab() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<RoleDraft>(BLANK_DRAFT);
  const [feedback, setFeedback] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["admin", "roles", "custom"],
    queryFn: fetchCustomRoles,
  });
  const permissionsQuery = useQuery({
    queryKey: ["admin", "roles", "permissions"],
    queryFn: fetchPermissionRegistry,
  });

  const roles = rolesQuery.data?.items ?? [];
  const permissionItems = permissionsQuery.data?.items ?? [];
  const grouped = useMemo(() => groupPermissions(permissionItems), [permissionItems]);
  const editorOpen = draft !== BLANK_DRAFT;
  const editingRole = draft.id !== null ? roles.find((role) => role.id === draft.id) ?? null : null;

  const refreshRoles = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin", "roles", "custom"] });
  };

  const saveMutation = useMutation({
    mutationFn: async (): Promise<void> => {
      const validationError = validateRoleDraft(draft);
      if (validationError) throw new Error(validationError);
      const payload = {
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        permissions: draft.permissions,
      };
      if (draft.id) {
        await updateCustomRole(draft.id, payload);
      } else {
        await createCustomRole(payload);
      }
    },
    onSuccess: async () => {
      setDraft(BLANK_DRAFT);
      setFeedback({
        tone: "success",
        text: draft.id ? "Custom role updated." : `Custom role "${draft.name.trim()}" created.`,
      });
      await refreshRoles();
    },
    onError: (err: unknown) => {
      const text =
        err instanceof ApiError && err.status === 409
          ? "A custom role with this name already exists."
          : errorMessage(err, "The role could not be saved.");
      setFeedback({ tone: "error", text });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) => deleteCustomRole(roleId),
    onSuccess: async (_result, roleId) => {
      if (draft.id === roleId) setDraft(BLANK_DRAFT);
      setPendingDeleteId(null);
      setFeedback({ tone: "success", text: "Custom role deleted." });
      await refreshRoles();
    },
    onError: (err: unknown, roleId) => {
      setPendingDeleteId(null);
      const text =
        err instanceof ApiError && err.status === 409
          ? "This role is assigned to users and cannot be deleted. Reassign those users first."
          : errorMessage(err, "The role could not be deleted.");
      setFeedback({ tone: "error", text });
      if (draft.id === roleId) setDraft(BLANK_DRAFT);
    },
  });

  const retryAll = () => {
    void rolesQuery.refetch();
    void permissionsQuery.refetch();
  };

  if (rolesQuery.isLoading || permissionsQuery.isLoading) {
    return (
      <div role="status" className="flex h-56 items-center justify-center gap-2 text-xs text-charcoal/50">
        <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
        Loading role designer…
      </div>
    );
  }

  if (rolesQuery.isError || permissionsQuery.isError) {
    return (
      <div role="alert" className="flex flex-col items-center justify-center rounded-2xl border border-rose-200 bg-white p-8 text-center">
        <AlertCircle aria-hidden="true" className="size-8 text-rose-500" />
        <h3 className="mt-2 text-base font-semibold text-charcoal">Failed to load role designer</h3>
        <p className="mt-1 text-xs text-charcoal/60">
          {errorMessage(rolesQuery.error ?? permissionsQuery.error, "A network or server error occurred.")}
        </p>
        <button type="button" onClick={retryAll} className="mt-4 inline-flex items-center gap-1.5 rounded-xl border border-charcoal/15 bg-white px-3.5 py-2 text-xs font-semibold text-charcoal hover:bg-charcoal/5">
          <RefreshCw aria-hidden="true" className="size-3.5" />
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
      {/* Role list */}
      <section aria-label="Custom roles" className="flex flex-col gap-3 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-xs">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-charcoal">
            <ShieldCheck aria-hidden="true" className="size-4 text-charcoal/60" />
            Custom roles
          </h2>
          <button
            type="button"
            onClick={() => { setDraft({ ...BLANK_DRAFT }); setFeedback(null); }}
            className="inline-flex items-center gap-1 rounded-lg bg-charcoal px-2.5 py-1.5 text-[11px] font-semibold text-ivory hover:opacity-95"
          >
            <Plus aria-hidden="true" className="size-3" />
            New
          </button>
        </div>

        {roles.length === 0 ? (
          <p className="rounded-xl border border-dashed border-charcoal/15 bg-charcoal/[0.02] px-3 py-6 text-center text-xs text-charcoal/55">
            No custom roles yet. Create one to grant a precise set of permissions without using a full administrator account.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {roles.map((role) => {
              const active = draft.id === role.id;
              return (
                <li key={role.id}>
                  <div
                    className={`flex w-full items-start justify-between gap-2 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                      active ? "border-charcoal bg-charcoal/5" : "border-charcoal/12 bg-white hover:border-charcoal/30"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => { setDraft(draftFromRole(role)); setFeedback(null); setPendingDeleteId(null); }}
                      className="min-w-0 flex-1"
                      aria-pressed={active}
                    >
                      <span className="block truncate text-xs font-bold text-charcoal">{role.name}</span>
                      {role.description && (
                        <span className="mt-0.5 block truncate text-[11px] text-charcoal/55">{role.description}</span>
                      )}
                      <span className="mt-1 block text-[10px] font-medium text-charcoal/45">
                        {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
                      </span>
                    </button>
                    {pendingDeleteId === role.id ? (
                      <span className="flex shrink-0 flex-col gap-1">
                        <button
                          type="button"
                          onClick={() => deleteMutation.mutate(role.id)}
                          disabled={deleteMutation.isPending}
                          className="rounded-lg bg-rose-600 px-2 py-1 text-[10px] font-bold text-white hover:bg-rose-700 disabled:opacity-50"
                        >
                          {deleteMutation.isPending ? "Deleting…" : "Confirm"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPendingDeleteId(null)}
                          className="rounded-lg border border-charcoal/15 px-2 py-1 text-[10px] font-semibold text-charcoal/70 hover:bg-charcoal/5"
                        >
                          Keep
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setPendingDeleteId(role.id)}
                        aria-label={`Delete role ${role.name}`}
                        title={deleteMutation.isPending ? "Delete in progress…" : "Delete role"}
                        className="shrink-0 rounded-lg p-1.5 text-charcoal/40 hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 aria-hidden="true" className="size-3.5" />
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <p className="mt-auto border-t border-charcoal/8 pt-2.5 text-[10px] leading-relaxed text-charcoal/45">
          Only inventory permissions are enforced today. Keys marked “not yet enforced” are saved and shown in the registry, but the matching modules still use built-in role gates.
        </p>
      </section>

      {/* Editor */}
      <section aria-label="Role editor" className="flex flex-col gap-4 rounded-2xl border border-charcoal/10 bg-white p-5 shadow-xs">
        {feedback && (
          <p
            role={feedback.tone === "error" ? "alert" : "status"}
            className={`flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-xs ${
              feedback.tone === "error"
                ? "border-rose-200 bg-rose-50 text-rose-800"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}
          >
            {feedback.tone === "error" ? (
              <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-rose-600" />
            ) : (
              <CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
            )}
            <span>{feedback.text}</span>
          </p>
        )}

        {!editorOpen ? (
          <div className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-charcoal/15 bg-charcoal/[0.02] px-6 py-10 text-center">
            <KeyRound aria-hidden="true" className="size-8 text-charcoal/30" />
            <p className="text-sm font-semibold text-charcoal">Design a custom role</p>
            <p className="max-w-sm text-xs leading-relaxed text-charcoal/55">
              Select a role from the list to edit it, or press “New” to build one from the permission checklist. Users keep their built-in base role for identity and scoping; the custom role adds the selected grants on top.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-charcoal">
                {editingRole ? `Editing “${editingRole.name}”` : "New custom role"}
              </h2>
              <button
                type="button"
                onClick={() => { setDraft(BLANK_DRAFT); setFeedback(null); }}
                aria-label="Close role editor"
                className="rounded-lg p-1.5 text-charcoal/40 hover:bg-charcoal/5 hover:text-charcoal"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="role-name" className="text-xs font-semibold text-charcoal">
                  Role name <span className="text-rose-500">*</span>
                </label>
                <input
                  id="role-name"
                  value={draft.name}
                  maxLength={64}
                  onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                  placeholder="e.g. Site Sales Lead"
                  className="h-10 rounded-xl border border-charcoal/15 bg-white px-3 text-sm text-charcoal placeholder:text-charcoal/40 focus:border-charcoal focus:outline-hidden focus:ring-2 focus:ring-charcoal/10"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="role-description" className="text-xs font-semibold text-charcoal">
                  Description (optional)
                </label>
                <input
                  id="role-description"
                  value={draft.description}
                  maxLength={255}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="What this role is allowed to do"
                  className="h-10 rounded-xl border border-charcoal/15 bg-white px-3 text-sm text-charcoal placeholder:text-charcoal/40 focus:border-charcoal focus:outline-hidden focus:ring-2 focus:ring-charcoal/10"
                />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-xl bg-charcoal/[0.04] px-3.5 py-2.5">
              <p className="text-[11px] font-medium text-charcoal/65">{summarizePermissions(draft.permissions, permissionItems)}</p>
              <p className={`text-[11px] font-bold ${draft.permissions.length > MAX_CUSTOM_ROLE_PERMISSIONS ? "text-rose-600" : "text-charcoal/50"}`}>
                {draft.permissions.length}/{MAX_CUSTOM_ROLE_PERMISSIONS}
              </p>
            </div>

            <fieldset className="flex flex-col gap-4">
              <legend className="sr-only">Permissions</legend>
              {grouped.length === 0 ? (
                <p role="status" className="rounded-xl border border-dashed border-charcoal/15 px-3 py-6 text-center text-xs text-charcoal/55">
                  The permission registry returned no entries.
                </p>
              ) : (
                grouped.map((groupEntry) => (
                  <div key={groupEntry.area}>
                    <h3 className="text-[11px] font-bold tracking-wider text-charcoal/55 uppercase">{areaLabel(groupEntry.area)}</h3>
                    <div className="mt-1.5 flex flex-col gap-1">
                      {groupEntry.permissions.map((permission) => {
                        const checked = draft.permissions.includes(permission.key);
                        const locked = !permission.grantable;
                        return (
                          <label
                            key={permission.key}
                            className={`flex items-start gap-2.5 rounded-xl border px-3 py-2 text-left transition-colors ${
                              locked
                                ? "cursor-not-allowed border-charcoal/8 bg-charcoal/[0.03] opacity-70"
                                : checked
                                  ? "cursor-pointer border-charcoal bg-charcoal/5"
                                  : "cursor-pointer border-charcoal/12 bg-white hover:border-charcoal/30"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={locked}
                              onChange={() =>
                                setDraft((current) => ({
                                  ...current,
                                  permissions: togglePermission(current.permissions, permission.key, permission.grantable),
                                }))
                              }
                              className="mt-0.5 size-4 rounded border-charcoal/30 accent-charcoal"
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-charcoal">
                                {permission.key}
                                {locked && (
                                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-amber-800 uppercase">
                                    <Lock aria-hidden="true" className="size-2.5" />
                                    System only
                                  </span>
                                )}
                                {!locked && !permission.enabled && (
                                  <span className="rounded-full border border-charcoal/15 bg-charcoal/5 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-charcoal/50 uppercase">
                                    Not yet enforced
                                  </span>
                                )}
                                {!locked && permission.enabled && (
                                  <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-emerald-800 uppercase">
                                    <BadgeCheck aria-hidden="true" className="size-2.5" />
                                    Enforced
                                  </span>
                                )}
                              </span>
                              <span className="mt-0.5 block text-[11px] leading-relaxed text-charcoal/55">{permission.description}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
            </fieldset>

            <div className="flex items-center justify-end gap-2.5 border-t border-charcoal/10 pt-4">
              <button
                type="button"
                onClick={() => { setDraft(BLANK_DRAFT); setFeedback(null); }}
                disabled={saveMutation.isPending}
                className="rounded-xl border border-charcoal/15 bg-white px-4 py-2 text-xs font-semibold text-charcoal hover:bg-charcoal/5 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => { setFeedback(null); saveMutation.mutate(); }}
                disabled={saveMutation.isPending || !draft.name.trim()}
                title={!draft.name.trim() ? "A role name is required" : undefined}
                className="inline-flex items-center gap-1.5 rounded-xl bg-charcoal px-4 py-2 text-xs font-semibold text-ivory shadow-xs hover:opacity-95 disabled:opacity-50"
              >
                {saveMutation.isPending && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" />}
                {saveMutation.isPending ? "Saving…" : editingRole ? "Save changes" : "Create role"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
