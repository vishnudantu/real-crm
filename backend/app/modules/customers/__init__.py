"""Canonical customer + opportunity graph (blueprint PF-008/PF-009, feature.md 16).

Single-source-of-truth invariants
---------------------------------
* ``leads`` stays the system of record for current intake flows; the customer
  graph sits ABOVE it. No existing endpoint behaviour changes.
* Money stays in ``postsales`` (sale_bookings/receipts). Messaging stays in
  ``conversations``/``omnichannel``. This module only references ids.
* ``Contact.canonical_key`` is a stable stored normalized identity string. It
  is the lexicographically lowest VERIFIED contact method value (prefixed
  ``email:`` / ``phone:``) when one exists, otherwise a generated
  ``uuid:<uuid4>`` assigned at creation. It never changes on merge; uniqueness
  is per tenant.
* ``ContactMethod.normalized_value`` is lowercase for EMAIL/social handles,
  digits-only (leading ``+`` kept) for PHONE/WHATSAPP_ID. Unique per
  (tenant_id, kind, normalized_value).
* ``Opportunity.lead_id`` back-references the originating lead; there is NO
  reverse column on ``leads`` (additive-only rule). 360 reads resolve via
  this back-reference.
* Merge is exact and reversible: ``ContactMerge.evidence`` records the moved
  method ids and repointed opportunity ids so ``unmerge_contacts`` restores
  byte-for-byte. Cross-tenant and self-merge are refused.
"""

from app.modules.customers.models import (
    Contact,
    ContactMerge,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    Opportunity,
    OpportunityStage,
    VerificationState,
)

__all__ = [
    "Contact",
    "ContactMerge",
    "ContactMethod",
    "ContactMethodKind",
    "ContactStatus",
    "Opportunity",
    "OpportunityStage",
    "VerificationState",
]
