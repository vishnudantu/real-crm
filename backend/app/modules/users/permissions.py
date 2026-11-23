"""Permission registry for tenant custom roles.

Only inventory is permission-gated in this foundation. Other keys describe the
next migration areas; their routers deliberately keep the existing built-in
role dependencies until each area is migrated. System keys are returned for UI
visibility but can never be assigned to a custom role.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.users.models import RoleName


@dataclass(frozen=True)
class PermissionDefinition:
    key: str
    area: str
    description: str
    legacy_roles: frozenset[str]
    grantable: bool = True


def _permission(
    area: str,
    action: str,
    description: str,
    *roles: RoleName,
    grantable: bool = True,
) -> PermissionDefinition:
    return PermissionDefinition(
        key=f"{area}.{action}",
        area=area,
        description=description,
        legacy_roles=frozenset(role.value for role in roles),
        grantable=grantable,
    )


def _build_permissions() -> tuple[PermissionDefinition, ...]:
    # Imported only while building the registry to avoid a models/permissions
    # import cycle; dependency checks use these static definitions thereafter.
    from app.modules.users.models import RoleName

    admin = RoleName.ADMIN
    manager = RoleName.MANAGER
    sales = RoleName.SALES_EXECUTIVE
    buyer = RoleName.BUYER
    return (
        _permission("inventory", "read", "View property units and availability.", admin, manager, sales, buyer),
        _permission("inventory", "write", "Create, edit, delete, and transition property units.", admin, manager),
        _permission("inventory", "holds", "Acquire, extend, release, reserve, and convert unit holds.", admin, manager, sales),
        _permission("projects", "read", "View projects and approved facts.", admin, sales),
        _permission("projects", "write", "Manage projects and project facts.", admin),
        _permission("leads", "read", "View leads and assignment history.", admin, sales),
        _permission("leads", "write", "Edit and advance assigned leads.", admin, sales),
        _permission("customers", "read", "View customer contacts and opportunities.", admin, sales),
        _permission("customers", "write", "Create, edit, and merge customer records.", admin, sales),
        _permission("bookings", "read", "View site visits and visit slots.", admin, sales),
        _permission("bookings", "write", "Schedule, reschedule, cancel, and review site visits.", admin, sales),
        _permission("brokers", "read", "View channel partners and performance.", admin, sales),
        _permission("brokers", "write", "Register and edit channel partners.", admin),
        _permission("postsales", "write", "Manage bookings, plans, installments, and receipts.", admin),
        _permission("postsales", "void_receipt", "Void a receipt with an auditable reversal.", admin),
        _permission("documents", "read", "View and download issued documents.", admin, sales),
        _permission("documents", "issue", "Prepare and issue demand letters and receipt PDFs.", admin),
        _permission("approvals", "request", "Open, view, and cancel approval requests.", admin, sales),
        _permission("approvals", "decide", "Approve or reject pending requests.", admin),
        _permission("deal_desk", "read", "View cost sheets, the discount matrix, and quotes.", admin, manager, sales),
        _permission("deal_desk", "manage", "Author cost sheets and edit the tenant discount matrix.", admin, manager),
        _permission("messaging", "send", "Send and test tenant messages.", admin),
        _permission("messaging", "configure", "Manage message templates, rules, and channel credentials.", admin),
        _permission("teamchat", "use", "Use internal staff team chat.", admin, sales),
        _permission("service_desk", "use", "Manage service-desk tickets and comments.", admin, sales),
        _permission("construction", "write", "Manage, update, and certify construction milestones.", admin),
        _permission("reconciliation", "write", "Import and reconcile bank transactions.", admin),
        _permission("voice_intel", "write", "Enqueue and process call transcriptions.", admin),
        _permission("settings", "manage", "Manage tenant and system settings.", admin, grantable=False),
        _permission("users", "manage", "Provision users and manage their account status.", admin, grantable=False),
        _permission("roles", "manage", "Design and assign custom roles.", admin, grantable=False),
        _permission("operator", "access", "Access the operator control plane and impersonation.", admin, grantable=False),
    )


_PERMISSIONS = _build_permissions()
PERMISSIONS = frozenset(_PERMISSIONS)
PERMISSION_REGISTRY = {item.key: item for item in _PERMISSIONS}
GRANTABLE_PERMISSIONS = frozenset(
    item.key for item in _PERMISSIONS if item.grantable
)
PROTECTED_PERMISSIONS = frozenset(
    item.key for item in _PERMISSIONS if not item.grantable
)

# Explicit compatibility map: legacy role gates only. Inventory is wired now;
# the remaining modules intentionally use require_roles until their own pilot.
PERMISSION_ROLE_GATES = {
    item.key: item.legacy_roles for item in _PERMISSIONS if item.grantable
}

INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"
INVENTORY_HOLDS = "inventory.holds"
APPROVALS_REQUEST = "approvals.request"
DEAL_DESK_READ = "deal_desk.read"
DEAL_DESK_MANAGE = "deal_desk.manage"


def validate_permissions(keys: list[str]) -> list[str]:
    """Return a stable de-duplicated list or reject unknown/system keys."""

    normalized = list(dict.fromkeys(key.strip() for key in keys))
    unknown = sorted(set(normalized) - PERMISSION_REGISTRY.keys())
    if unknown:
        raise ValueError(f"Unknown permission keys: {', '.join(unknown)}")
    protected = sorted(set(normalized) & PROTECTED_PERMISSIONS)
    if protected:
        raise ValueError(
            f"System permissions cannot be granted to custom roles: {', '.join(protected)}"
        )
    return normalized
