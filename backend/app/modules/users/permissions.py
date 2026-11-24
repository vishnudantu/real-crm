"""Permission registry for tenant custom roles.

Tenant business routers gate staff-only endpoints with ``require_permission``;
``ENABLED_PERMISSION_KEYS`` marks exactly the keys wired that way today, so the
role designer UI only reports what truly controls access. Endpoints genuinely
shared with buyers (public lead intake, ``/leads/mine`` and opt-out, buyer
conversation start/list/get/messages and handoff requests, site-visit booking
and evidence, project and fact browsing, own-contact views, the sale-booking
detail/ledger, and visit slots) deliberately stay open CurrentUser endpoints
whose services scope rows by identity — a staff-only key must never sit in
front of a buyer flow. Keys for staff surfaces that stay service-gated
(bookings.read/write, projects.read, conversations.use) remain registered but
unwired metadata until a require_permission endpoint exists there. System keys
(settings/users/roles/operator) are admin-only by design: their routers keep
``require_roles(ADMIN)``, which custom-role users can never inherit.

Base-role semantics: assigning a custom role never changes a user's built-in
role. The built-in role stays the identity used for row-level service scoping
(an ADMIN with a custom role stays tenant-wide; a SALES_EXECUTIVE with one
stays executive-scoped); the custom role adds capability grants on top.
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
        _permission("leads", "manage", "Assign leads, check duplicates, and read the opt-out register.", admin),
        _permission("customers", "read", "View customer contacts and opportunities.", admin, sales),
        _permission("customers", "write", "Create, edit, and merge customer records.", admin, sales),
        _permission("bookings", "read", "View site visits and visit slots.", admin, sales),
        _permission("bookings", "write", "Schedule, reschedule, cancel, and review site visits.", admin, sales),
        _permission("follow_ups", "use", "Schedule, edit, complete, and cancel lead follow-ups.", admin, sales),
        _permission("handoffs", "use", "Progress and resolve human handoffs.", admin, sales),
        _permission("conversations", "use", "Manage staff-side conversation threads.", admin, sales),
        _permission("brokers", "read", "View channel partners and performance.", admin, sales),
        _permission("brokers", "write", "Register and edit channel partners.", admin),
        _permission("postsales", "read", "View sale bookings, ledgers, and receipts.", admin, sales),
        _permission("postsales", "write", "Manage bookings, plans, installments, and receipts.", admin),
        _permission("postsales", "void_receipt", "Void a receipt with an auditable reversal.", admin),
        _permission("documents", "read", "View and download issued documents.", admin, sales),
        _permission("documents", "prepare", "Stage demand letters for approval.", admin, sales),
        _permission("documents", "issue", "Issue and void demand letters and receipt PDFs.", admin),
        _permission("approvals", "request", "Open, view, and cancel approval requests.", admin, sales),
        _permission("approvals", "decide", "Approve or reject pending requests.", admin),
        _permission("deal_desk", "read", "View cost sheets, the discount matrix, and quotes.", admin, manager, sales),
        _permission("deal_desk", "manage", "Author cost sheets and edit the tenant discount matrix.", admin, manager),
        _permission("messaging", "send", "Send and test tenant messages.", admin),
        _permission("messaging", "configure", "Manage message templates, rules, and channel credentials.", admin),
        _permission("teamchat", "use", "Use internal staff team chat.", admin, sales),
        _permission("service_desk", "use", "Manage service-desk tickets and comments.", admin, sales),
        _permission("construction", "read", "View construction milestones and progress.", admin, sales),
        _permission("construction", "write", "Manage, update, and certify construction milestones.", admin),
        _permission("reconciliation", "read", "View bank transactions and the exception queue.", admin, sales),
        _permission("reconciliation", "write", "Import and reconcile bank transactions.", admin),
        _permission("voice_intel", "read", "View call transcripts and summaries.", admin, sales),
        _permission("voice_intel", "write", "Enqueue and process call transcriptions.", admin),
        _permission("tenant_ai", "manage", "Configure the tenant's AI provider credentials.", admin),
        _permission("integrations", "manage", "Manage external integration connections and credentials.", admin),
        _permission("city_intel", "read", "View locality demand, amenities, and locality reports.", admin, sales),
        _permission("city_intel", "manage", "Curate project amenities and author locality reports.", admin),
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

# Explicit compatibility map: legacy role gates only.
PERMISSION_ROLE_GATES = {
    item.key: item.legacy_roles for item in _PERMISSIONS if item.grantable
}

INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"
INVENTORY_HOLDS = "inventory.holds"
PROJECTS_WRITE = "projects.write"
LEADS_READ = "leads.read"
LEADS_WRITE = "leads.write"
LEADS_MANAGE = "leads.manage"
CUSTOMERS_READ = "customers.read"
CUSTOMERS_WRITE = "customers.write"
BOOKINGS_WRITE = "bookings.write"
FOLLOW_UPS_USE = "follow_ups.use"
HANDOFFS_USE = "handoffs.use"
CONVERSATIONS_USE = "conversations.use"
BROKERS_READ = "brokers.read"
BROKERS_WRITE = "brokers.write"
POSTSALES_READ = "postsales.read"
POSTSALES_WRITE = "postsales.write"
POSTSALES_VOID_RECEIPT = "postsales.void_receipt"
DOCUMENTS_READ = "documents.read"
DOCUMENTS_PREPARE = "documents.prepare"
DOCUMENTS_ISSUE = "documents.issue"
APPROVALS_REQUEST = "approvals.request"
APPROVALS_DECIDE = "approvals.decide"
MESSAGING_SEND = "messaging.send"
MESSAGING_CONFIGURE = "messaging.configure"
TEAMCHAT_USE = "teamchat.use"
SERVICE_DESK_USE = "service_desk.use"
CONSTRUCTION_READ = "construction.read"
CONSTRUCTION_WRITE = "construction.write"
RECONCILIATION_READ = "reconciliation.read"
RECONCILIATION_WRITE = "reconciliation.write"
VOICE_INTEL_READ = "voice_intel.read"
VOICE_INTEL_WRITE = "voice_intel.write"
TENANT_AI_MANAGE = "tenant_ai.manage"
INTEGRATIONS_MANAGE = "integrations.manage"
DEAL_DESK_READ = "deal_desk.read"
DEAL_DESK_MANAGE = "deal_desk.manage"
CITY_INTEL_READ = "city_intel.read"
CITY_INTEL_MANAGE = "city_intel.manage"

# The exact keys whose routers now enforce require_permission instead of a
# legacy role gate. The role designer UI reports enabled status from this set;
# registered-but-unwired keys (buyer-shared surfaces kept open as built-in
# CurrentUser endpoints: projects.read, bookings.read/write, conversations.use,
# handoffs.use) are intentionally absent.
ENABLED_PERMISSION_KEYS = frozenset(
    {
        INVENTORY_READ,
        INVENTORY_WRITE,
        INVENTORY_HOLDS,
        PROJECTS_WRITE,
        LEADS_READ,
        LEADS_WRITE,
        LEADS_MANAGE,
        CUSTOMERS_READ,
        CUSTOMERS_WRITE,
        FOLLOW_UPS_USE,
        BROKERS_READ,
        BROKERS_WRITE,
        POSTSALES_READ,
        POSTSALES_WRITE,
        POSTSALES_VOID_RECEIPT,
        DOCUMENTS_READ,
        DOCUMENTS_PREPARE,
        DOCUMENTS_ISSUE,
        APPROVALS_REQUEST,
        APPROVALS_DECIDE,
        MESSAGING_SEND,
        MESSAGING_CONFIGURE,
        TEAMCHAT_USE,
        SERVICE_DESK_USE,
        CONSTRUCTION_READ,
        CONSTRUCTION_WRITE,
        RECONCILIATION_READ,
        RECONCILIATION_WRITE,
        VOICE_INTEL_READ,
        VOICE_INTEL_WRITE,
        TENANT_AI_MANAGE,
        INTEGRATIONS_MANAGE,
        DEAL_DESK_READ,
        DEAL_DESK_MANAGE,
        CITY_INTEL_READ,
        CITY_INTEL_MANAGE,
    }
)


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
