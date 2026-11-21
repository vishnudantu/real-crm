import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  LoaderCircle,
  Pencil,
  Plus,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import {
  createOperatorUser,
  fetchOperatorUsers,
  updateOperatorUser,
} from "./api";
import { errorMessage } from "../shared/apiRequest";
import { formatDateTime } from "./format";
import type {
  OperatorPermission,
  OperatorRole,
  OperatorUser,
} from "./operatorModel";
import {
  ErrorBlock,
  InlineNotice,
  LoadingBlock,
  Modal,
  SectionHeader,
  StatusBadge,
  Surface,
  inputClasses,
  labelClasses,
  primaryButtonClasses,
  secondaryButtonClasses,
} from "./ui";

const ROLES: { value: OperatorRole; label: string; description: string }[] = [
  { value: "OWNER", label: "Owner", description: "Full control-plane access" },
  { value: "SUPPORT", label: "Support", description: "Read tenants and audit history" },
  { value: "SALES", label: "Sales", description: "Read and provision tenants" },
  { value: "DEPLOYER", label: "Deployer", description: "Read tenants and request deployments" },
];

const PERMISSIONS: { value: OperatorPermission; label: string }[] = [
  { value: "tenants.read", label: "Read tenants and plans" },
  { value: "tenants.write", label: "Provision and update tenants" },
  { value: "plans.write", label: "Manage subscription plans" },
  { value: "deployments.write", label: "Request deployments" },
  { value: "operators.manage", label: "Manage operator accounts" },
  { value: "audit.read", label: "Read audit logs" },
];

const operatorSchema = z.object({
  fullName: z.string().trim().min(2, "Enter the operator's full name.").max(255),
  email: z.string().trim().email("Enter a valid email address."),
  password: z
    .string()
    .min(12, "Use at least 12 characters.")
    .max(128)
    .regex(/[a-z]/, "Include a lowercase letter.")
    .regex(/[A-Z]/, "Include an uppercase letter.")
    .regex(/\d/, "Include a number.")
    .regex(/[^A-Za-z0-9]/, "Include a symbol."),
  role: z.enum(["OWNER", "SUPPORT", "SALES", "DEPLOYER"]),
  permissions: z.array(z.string()),
});

type OperatorFormValues = z.infer<typeof operatorSchema>;

export function OperatorUsersPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<OperatorUser | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const usersQuery = useQuery({
    queryKey: ["operator", "operators"],
    queryFn: fetchOperatorUsers,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-[0.2em] text-forest uppercase">
            Access control
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-charcoal sm:text-3xl">
            Operator accounts
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-charcoal/60">
            Manage the people who can administer PropFlow tenants, plans, and
            deployments. Operator accounts are separate from tenant users.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setNotice(null);
            setEditing("new");
          }}
          className={primaryButtonClasses}
        >
          <Plus aria-hidden="true" className="size-4" />
          Add operator
        </button>
      </div>

      {notice ? <InlineNotice tone="success">{notice}</InlineNotice> : null}

      <Surface>
        <SectionHeader
          eyebrow="Privileged identities"
          title={`${usersQuery.data?.length ?? 0} operators`}
          description="Roles grant a base permission set. Additional permissions can be granted individually."
        />
        {usersQuery.isLoading ? (
          <LoadingBlock label="Loading operator accounts…" />
        ) : usersQuery.isError ? (
          <ErrorBlock
            message={
              usersQuery.error instanceof Error
                ? usersQuery.error.message
                : "Failed to load operators."
            }
            onRetry={() => void usersQuery.refetch()}
          />
        ) : (
          <div className="divide-y divide-charcoal/10">
            {(usersQuery.data ?? []).map((operator) => (
              <div
                key={operator.id}
                className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:px-6"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-charcoal/5 text-sm font-bold text-charcoal/65">
                  {operator.full_name
                    .split(/\s+/)
                    .map((part) => part[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-charcoal">
                      {operator.full_name}
                    </p>
                    <span className="rounded-full border border-charcoal/10 bg-charcoal/5 px-2 py-0.5 text-[0.6rem] font-semibold tracking-wider text-charcoal/60">
                      {operator.role}
                    </span>
                    <StatusBadge status={operator.is_active ? "active" : "inactive"} />
                  </div>
                  <p className="mt-1 truncate text-xs text-charcoal/55">{operator.email}</p>
                  <p className="mt-1 text-[0.65rem] text-charcoal/45">
                    Last sign in: {formatDateTime(operator.last_login_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setNotice(null);
                    setEditing(operator);
                  }}
                  className={`${secondaryButtonClasses} self-start sm:self-center`}
                >
                  <Pencil aria-hidden="true" className="size-3.5" />
                  Edit access
                </button>
              </div>
            ))}
          </div>
        )}
      </Surface>

      {editing ? (
        <OperatorEditorModal
          operator={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (message) => {
            setEditing(null);
            setNotice(message);
            await queryClient.invalidateQueries({ queryKey: ["operator", "operators"] });
          }}
        />
      ) : null}
    </div>
  );
}

interface OperatorEditorModalProps {
  operator: OperatorUser | null;
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}

function OperatorEditorModal({
  operator,
  onClose,
  onSaved,
}: OperatorEditorModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(operator?.is_active ?? true);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<OperatorFormValues>({
    resolver: zodResolver(operatorSchema),
    defaultValues: {
      fullName: operator?.full_name ?? "",
      email: operator?.email ?? "",
      password: "",
      role: operator?.role ?? "SUPPORT",
      permissions: operator?.permissions ?? [],
    },
  });

  const mutation = useMutation({
    mutationFn: async (values: OperatorFormValues) => {
      if (operator) {
        return updateOperatorUser(operator.id, {
          role: values.role,
          permissions: values.permissions,
          is_active: isActive,
        });
      }
      return createOperatorUser({
        full_name: values.fullName.trim(),
        email: values.email.trim().toLowerCase(),
        password: values.password,
        role: values.role,
        permissions: values.permissions,
      });
    },
    onSuccess: async (saved) => {
      await onSaved(operator ? `${saved.full_name}'s access was updated.` : `${saved.full_name} was added as an operator.`);
    },
    onError: (submitError: unknown) => {
      setError(errorMessage(submitError, "Failed to save operator account."));
    },
  });

  return (
    <Modal
      title={operator ? `Edit ${operator.full_name}` : "Add operator"}
      description="Assign a role and any additional control-plane permissions."
      onClose={onClose}
    >
      <form noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}

        {!operator ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="new-operator-name" className={labelClasses}>Full name</label>
              <input id="new-operator-name" className={inputClasses} {...register("fullName")} />
              {errors.fullName ? <p className="mt-1.5 text-xs text-clay">{errors.fullName.message}</p> : null}
            </div>
            <div>
              <label htmlFor="new-operator-email" className={labelClasses}>Email address</label>
              <input id="new-operator-email" type="email" className={inputClasses} {...register("email")} />
              {errors.email ? <p className="mt-1.5 text-xs text-clay">{errors.email.message}</p> : null}
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="new-operator-password" className={labelClasses}>Temporary password</label>
              <input
                id="new-operator-password"
                type="password"
                autoComplete="new-password"
                className={inputClasses}
                {...register("password")}
              />
              <p className="mt-1.5 text-xs text-charcoal/50">
                At least 12 characters with uppercase, lowercase, a number, and a symbol.
              </p>
              {errors.password ? <p className="mt-1.5 text-xs text-clay">{errors.password.message}</p> : null}
            </div>
          </div>
        ) : (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-charcoal/10 bg-charcoal/[0.03] p-3.5">
            <UserCog aria-hidden="true" className="size-5 text-charcoal/45" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{operator.full_name}</p>
              <p className="truncate text-xs text-charcoal/55">{operator.email}</p>
            </div>
          </div>
        )}

        <div className="mt-4">
          <span className={labelClasses}>Role</span>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {ROLES.map((role) => (
              <label
                key={role.value}
                className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-charcoal/10 bg-white p-3 transition-colors has-checked:border-forest/40 has-checked:bg-forest/5"
              >
                <input
                  type="radio"
                  value={role.value}
                  className="mt-0.5 size-4 accent-forest"
                  {...register("role")}
                />
                <span>
                  <span className="block text-xs font-semibold text-charcoal">{role.label}</span>
                  <span className="mt-0.5 block text-[0.65rem] leading-4 text-charcoal/55">
                    {role.description}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <fieldset className="mt-5">
          <legend className="text-xs font-semibold text-charcoal/75">
            Additional permissions
          </legend>
          <p className="mt-1 text-[0.65rem] text-charcoal/50">
            These permissions are added to those already granted by the role.
          </p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {PERMISSIONS.map((permission) => (
              <label
                key={permission.value}
                className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white px-3 py-2.5 text-xs font-medium text-charcoal/75 has-checked:border-forest/30 has-checked:bg-forest/5"
              >
                <input
                  type="checkbox"
                  value={permission.value}
                  className="size-4 accent-forest"
                  {...register("permissions")}
                />
                {permission.label}
              </label>
            ))}
          </div>
        </fieldset>

        {operator ? (
          <label className="mt-5 flex cursor-pointer items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white p-3 text-xs font-semibold text-charcoal">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              className="size-4 accent-forest"
            />
            Account can sign in to the operator console
          </label>
        ) : null}

        <div className="mt-6 flex flex-col-reverse gap-3 border-t border-charcoal/10 pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className={secondaryButtonClasses}>
            Cancel
          </button>
          <button type="submit" disabled={isSubmitting || mutation.isPending} className={primaryButtonClasses}>
            {isSubmitting || mutation.isPending ? (
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <ShieldCheck aria-hidden="true" className="size-4" />
            )}
            {operator ? "Save access changes" : "Create operator"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
