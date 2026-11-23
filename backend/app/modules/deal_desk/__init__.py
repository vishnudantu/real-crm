"""Deal desk: cost sheets, per-tenant discount approval matrix, quotes.

Builds on the approvals engine: a quote raised into approval creates a
DEAL_DISCOUNT request whose APPROVE decision (dispatched from
app.modules.approvals.side_effects) writes the approved discount onto the
unit. Discounts change the consideration at booking time; they never mutate
postsales money.
"""

from app.modules.deal_desk import models, repository, schemas, service  # noqa: F401

__all__ = ["models", "repository", "schemas", "service"]
