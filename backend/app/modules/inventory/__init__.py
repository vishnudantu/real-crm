"""Property inventory: canonical units, availability state machine, atomic holds.

Invariants enforced by the DATABASE (hold even if service code changes):
1. One canonical unit identity per project: UNIQUE (tenant_id, project_id,
   internal_code) on property_units.
2. At most one ACTIVE hold per unit, ever: partial unique index on
   unit_holds (tenant_id, unit_id) WHERE state = 'ACTIVE' — second concurrent
   claim raises IntegrityError on SQLite and PostgreSQL alike.
3. Hold exclusivity window is closed: unit status is a CHECK-constrained
   enum; every state change appends an immutable unit_status_events row in
   the same transaction (append-only audit evidence).
4. Holds are tenant-owned rows (TenantOwned); cross-tenant reads are 404s,
   enforced by explicit tenant predicates in every repository query.
5. Hold lifecycle is machine-checked: state enum CHECK + extension_count
   CHECK (<= 2) + release_source CHECK; expiry/release/convert only move
   ACTIVE holds.

Invariants enforced by the SERVICE (transition map + locking):
6. RESERVED/BOOKED are reachable only via reserve/convert paths (event-source
   gating in ALLOWED_TRANSITIONS); AVAILABLE->ON_HOLD and back only via the
   hold services under the tenant+unit advisory lock (PostgreSQL) or process
   lock (SQLite).

Deferred (explicitly NOT in this slice): pricing and price books, CSV bulk
import parsing, scheduler auto-wiring of expire_holds (the function is
callable now), opportunity_ref FK to customers.
"""

from app.modules.inventory import models, repository, schemas, service  # noqa: F401

__all__ = ["models", "repository", "schemas", "service"]
