# PropFlow — Current State Audit (Phase 0)

**Date:** 2026-11-22 · **Branch:** `main` @ `2614ffc` (supersedes blueprint-reviewed `a7fa516`)
**Method:** executed test suites, live server checks, and source inspection.
This audit verifies the `PROPFLOW_MASTER_BLUEPRINT_FOR_CLAUDE_CODE.md` findings against
the checked-out code. Confirmed / refuted / new items are labeled as such.

## 1. Verified working baseline

| Check | Result |
| --- | --- |
| Backend pytest (Python 3.13, local venv) | **350 passed, 0 failed, 0 skipped** (blueprint baseline was 292) |
| Frontend `tsc --noEmit && vite build` | Passes |
| Frontend unit tests (`node --test`) | 7 passed |
| Live widget end-to-end (embed.js → session → chat → consent-gated lead) | Passes against running dev API |
| Live demo login round-trip (tenant admin → feature resolution) | Passes |
| Alembic | Single linear head applied; `alembic check` clean on dev DB |
| Dependencies | `cryptography==50.0.2`, `livekit-api==2.0.1` installed and pinned in `requirements.txt` |
| Production config validation | `ENCRYPTION_KEY` now **required** in production; placeholder JWT rejected |

### New since the blueprint was written (`2614ffc`, omnichannel vertical slice)

- **Omnichannel module**: unified inbox model for WEB_CHAT / WhatsApp / Instagram /
  Messenger + calls; per-tenant **encrypted** channel credentials (Fernet, tenant-scoped
  key derivation); Meta webhook signature verification with HMAC; idempotent message
  ingestion (unique external id per tenant); DPDP-safe inbound lead creation
  (`consent_to_contact=False` for enquiry-only capture).
- **Website widget**: per-tenant `embed.js` (white-label bubble + contact form),
  visitor sessions via widget-audience JWT, AI replies through the existing approved-facts
  boundary, rate limiting, consent-gated lead capture.
- **Calling**: LiveKit adapter (participant tokens, async Egress) + simulated provider;
  recording requires explicit consent confirmation.
- **Per-tenant feature flags**: 17-feature catalog, operator overrides, plan features,
  one-step tenant onboarding wizard; enforced on authenticated endpoints (404), public
  webhooks, outbound replies, and the widget itself.
- **Two-zone CORS**: widget paths permissive without credentials; API allowlist unchanged.
- **Brand sweep**: no Keylo/Ahmedabad references remain in tracked markdown/assets.

## 2. Blueprint P0 findings — verification status

| ID | Claim | Verdict | Evidence |
| --- | --- | --- | --- |
| P0.1 | No authoritative unit inventory; `unit_number` is free text, double-allocation possible | **CONFIRMED** | `postsales/models.py` `SaleBooking.unit_number: String(64)`; `create_booking` checks only lead-uniqueness (`ix_sale_bookings_tenant_lead`), never unit uniqueness |
| P0.2 | Receipt number from `count+1` and balance check without locks → duplicate numbers / overpayment races | **CONFIRMED — being fixed by this slice** | `postsales/service.py` `record_receipt()` (was lines 161–226): `paid` sum read then receipt `count+1`, no `FOR UPDATE`/advisory lock; unique constraint `uq_receipts_tenant_number` exists so a race surfaces as a crash (500), not corruption — still a P0 availability + correctness bug |
| P0.3 | Demand letter = timestamp flag, no document artifact | **CONFIRMED** | `send_demand_letter()` sets `demand_letter_sent_at` only |
| P0.4 | Dispatcher does not re-check consent at send time | **CONFIRMED** | `messaging/dispatcher.py` `process_due_deliveries()` calls provider directly; no lead consent/opt-out lookup before send |
| P0.5 | Connector sets `consent_to_contact=True` without evidence | **CONFIRMED** | `connectors/service.py` `ingest_lead()` hardcodes `consent_to_contact=True` |
| P0.6 | Meta page-mapping lookup mismatch | **PARTIALLY CONFIRMED (worse)** | `connectors/router.py` `_active_project_for_meta()` does `session.get(SystemSetting, ("default", "meta_page_projects"))` — "default" is a literal tenant id, so any tenant other than a tenant literally identified that way can never resolve a mapping. Additionally the webhook verifies signatures with the **global** `settings.meta_app_secret`, not a per-tenant secret — conflicts with multi-tenant Meta connections (ties to the requested one-click Meta/Google Ads connect) |
| P0.7 | Connector dedupe (AND) disagrees with lead dedupe (OR) | **CONFIRMED** | `connectors/service.py` builds `conditions=[tenant, email?, phone?]` all ANDed; `leads/service.py` `_raise_if_duplicate` uses OR semantics |
| P0.8 | Billing limits count lifetime rows, not per-period usage | **CONFIRMED** | `billing/service.py` `ensure_within_plan_limits()`: `count(Lead.id)` and `count(MessageDelivery … status=SENT)` with **no date filter** against fields named `*_per_month` |
| P0.9 | Razorpay event idempotency/ordering unproven | **NOT REPRODUCED** (hypothesis stands) | `billing/service.py` computes event ids and guards replays in `process_webhook`; needs the blueprint's formal reconciliation test before any claim |

## 3. Blueprint P1 notes — corrections found during verification

- **P1.3 nuance (refuted as a leak, confirmed as dead code):** `TENANT_TABLES` in
  `app/db/tenancy.py` and `with_tenant()` are **not consumed by any runtime filter** —
  a repo-wide search shows usage only in their own definition and unit tests of
  `with_tenant`. `db.info["tenant_id"]` is set by auth but read nowhere. So the newer
  messaging/omnichannel tables missing from the set cause **no access leak**; the risk is
  the opposite: developers may trust a guard that doesn't exist. Isolation is currently
  enforced correctly per-service by explicit `tenant_id` predicates, and tenant isolation
  tests pass. Action item: add a CI schema-introspection test that every `TenantOwned`
  table is query-scoped, instead of reviving the dead set.
- **Precedent for P0.2 fix pattern exists in-repo:** `leads/service.py` `_lock_contact_keys`
  uses `pg_advisory_xact_lock` on PostgreSQL with an in-process `threading.Lock` fallback
  for SQLite tests (`test_concurrent_duplicate_creation` proves the pattern). The receipt
  fix mirrors this exact house style.
- Global unique `User.email` (P1.1), coarse roles (P1.2), CI gaps (P1.5), doc drift (P1.6)
  — all confirmed by inspection. (P1.6 partially addressed: brand sweep in `2614ffc`;
  `PROJECT.md`/`BUILD_SPEC.md` historical statements still need a superseded banner.)

## 4. Where the omnichannel slice intersects blueprint findings (self-assessment)

- Widget inbound leads: consent-safe by design (inbound ≠ marketing consent) ✅ aligns with P0.5 intent, but connector/Meta-ads intake still hardcodes `True` (P0.5 open).
- Channel webhooks verify HMAC per tenant ✅ (better than legacy Meta-ads path, P0.6).
- Omnichannel outbound replies send immediately without a future consent-window policy — acceptable for 24-hour service-window channels, but a Meta policy window check is a Phase-4 hardening item.
- Simulated providers are clearly labeled as simulated in API (`provider=simulated`) and UI (amber SIMULATED badge) ✅ per rule 9.

## 5. Open risks before public onboarding (unchanged by this repo's code)

1. No public HTTPS domain yet (Meta webhooks + LiveKit require one).
2. No real Meta app / WhatsApp BSP / LiveKit server configured; sandbox live-testing pending.
3. No production Postgres, backups, or monitoring yet (see 50–100 client sizing below).
4. P0.1/P0.3–P0.8 above remain to be fixed, in blueprint order.

## 6. Server sizing (operational reference, 50–100 tenants)

- App tier: 2× (4 vCPU / 8 GB) behind a load balancer (FastAPI workers + Nginx), or one
  beefy 8 vCPU / 16 GB box to start.
- PostgreSQL 16: managed, 4 vCPU / 16 GB / 200 GB SSD, PITR backups + tested restores.
- Redis (queue/cache/rate-limits): small managed instance when workers are split out.
- LiveKit: separate 2–4 vCPU / 4 GB media node(s); egress/recording is CPU-bound.
- Object storage (recordings, demand-letter PDFs): S3-compatible, tenant-prefixed,
  signed URLs (per blueprint 18.1).
- CI: add frontend unit + Playwright E2E + dependency/secret scanning (blueprint P1.5).

## 7. Next single task

**PF-002 (this slice):** make installment receipt posting concurrency-safe, uniquely
numbered, and idempotent, preserving APIs and tenant boundaries. Immediately after:
**PF-003** dispatch-time consent gate, then **PF-004/P0.6** durable integration
connections (this is also where the requested one-click Meta/Google Ads connect lands),
then **PF-005** per-period billing meters. Inventory (PF-010) starts right after the
privacy/consent P0s, per the blueprint's priority rules.
