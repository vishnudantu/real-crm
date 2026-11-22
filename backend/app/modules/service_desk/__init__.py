"""Customer service desk: support tickets with SLA tracking.

Scope of this foundation:
  * Staff-only ticket queue (ADMIN and SALES_EXECUTIVE); a buyer self-service
    portal is deliberately out of scope and will reuse these services with a
    customer predicate later.
  * SLA deadlines derived from priority at creation; no SLA pause/resume clock.
  * Staff-first intake only (no email/WhatsApp omnichannel ingestion yet) and
    no field dispatch workflows.
"""
