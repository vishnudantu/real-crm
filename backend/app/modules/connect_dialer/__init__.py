"""Connect dialer: call dispositions, DNC suppression, and a live wallboard.

Builds on the existing omnichannel LiveKit calling (CallRecord) without changing
the telephony provider. Adds the contact-centre controls the product needs:
- A disposition recorded against a completed call (Interested, Callback, etc.).
- A per-tenant Do-Not-Call suppression list enforced before dialing.
- Scheduled callbacks with assignment + reminder timestamps.
- A wallboard read-model aggregating live call/agent state for supervisors.
"""
