"""Unit tests for the customer + opportunity graph service (PF-008/009)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.service import create_user_with_role
from app.modules.customers import service
from app.modules.customers.exceptions import (
    ContactNotFoundError,
    ContactUpdateError,
    CustomerAccessDeniedError,
    InvalidStageTransitionError,
    MergeError,
)
from app.modules.customers.models import (
    Contact,
    ContactMerge,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    Opportunity,
    OpportunityStage,
    VerificationState,
    utcnow,
)
from app.modules.leads.models import Lead, LeadSource
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


@pytest.fixture()
def env(test_session_factory: sessionmaker[Session], seeded_roles: None) -> dict:
    with test_session_factory() as session:
        tenant = Tenant(slug=f"t-{uuid4().hex[:8]}", name="T")
        session.add(tenant)
        session.flush()
        admin = create_user_with_role(
            session,
            full_name="Admin",
            email=f"admin-{uuid4().hex[:8]}@ex.com",
            password=TEST_PASSWORD,
            role_name=RoleName.ADMIN,
            tenant_id=tenant.id,
        )
        project = Project(
            tenant_id=tenant.id,
            name="P",
            slug=f"p-{uuid4().hex[:8]}",
            location="X",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        session.add(project)
        project2 = Project(
            tenant_id=tenant.id,
            name="P2",
            slug=f"p2-{uuid4().hex[:8]}",
            location="X",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        session.add(project2)
        session.commit()
        return {
            "factory": test_session_factory,
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "project_id": project.id,
            "project2_id": project2.id,
        }


def _actor(session: Session, env: dict) -> User:
    return session.get(User, env["admin_id"])


def _contact(session: Session, tenant_id, *, email=None, phone=None, name="C"):
    contact, method, created = service.resolve_contact(
        session, tenant_id=tenant_id, email=email, phone=phone, display_name=name
    )
    session.commit()
    return contact


class TestResolveContact:
    def test_create_then_exact_email_match_case_whitespace(self, env) -> None:
        with env["factory"]() as s:
            c1 = _contact(s, env["tenant_id"], email="  Alice@Example.COM  ")
            s.expunge_all()
            c2, m2, created2 = service.resolve_contact(
                s, tenant_id=env["tenant_id"], email="alice@example.com"
            )
            assert created2 is False
            assert c2.id == c1.id
            assert m2.normalized_value == "alice@example.com"

    def test_phone_format_normalization(self, env) -> None:
        with env["factory"]() as s:
            c1 = _contact(s, env["tenant_id"], phone="+91 96115 02119")
            s.expunge_all()
            c2, _, created2 = service.resolve_contact(
                s, tenant_id=env["tenant_id"], phone="+91-96115-02119"
            )
            assert created2 is False
            assert c2.id == c1.id

    def test_new_contact_when_no_match(self, env) -> None:
        with env["factory"]() as s:
            c, m, created = service.resolve_contact(
                s, tenant_id=env["tenant_id"], email="new@ex.com"
            )
            assert created is True
            assert m.is_primary is True
            assert c.canonical_key.startswith("uuid:")

    def test_tenant_isolation(self, env) -> None:
        with env["factory"]() as s:
            other = Tenant(slug=f"o-{uuid4().hex[:8]}", name="O")
            s.add(other)
            s.flush()
            _contact(s, env["tenant_id"], email="shared@ex.com")
            c2, _, created2 = service.resolve_contact(
                s, tenant_id=other.id, email="shared@ex.com"
            )
            assert created2 is True  # same email in different tenant = new


class TestSuggestDuplicates:
    def test_exact_email_match(self, env) -> None:
        with env["factory"]() as s:
            c1 = _contact(s, env["tenant_id"], email="dup@ex.com", name="A")
            # second contact same email can't exist via resolve (it would match),
            # so construct manually with a different phone to simulate drift.
            c2 = Contact(
                tenant_id=env["tenant_id"],
                canonical_key=f"uuid:{uuid4()}",
                display_name="B",
            )
            s.add(c2)
            s.flush()
            s.add(
                ContactMethod(
                    tenant_id=env["tenant_id"],
                    contact_id=c2.id,
                    kind=ContactMethodKind.PHONE.value,
                    value="+919999999999",
                    normalized_value="+919999999999",
                    is_primary=True,
                )
            )
            # give c1 a phone too, then point a second EMAIL at c2 manually is
            # blocked by unique; instead test HIGH phone-suffix evidence.
            s.add(
                ContactMethod(
                    tenant_id=env["tenant_id"],
                    contact_id=c1.id,
                    kind=ContactMethodKind.WHATSAPP_ID.value,
                    value="9999999999",
                    normalized_value="9999999999",
                )
            )
            s.commit()
            result = service.suggest_duplicates(
                s, tenant_id=env["tenant_id"], contact_id=c1.id
            )
            assert any(
                cand.contact_id == c2.id and cand.confidence == "HIGH"
                for cand in result.candidates
            )


class TestMergeUnmerge:
    def test_merge_moves_methods_and_opportunities_then_unmerge_restores(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            survivor = _contact(s, env["tenant_id"], email="s@ex.com", name="S")
            merged = _contact(s, env["tenant_id"], email="m@ex.com", name="M")
            merged_phone = ContactMethod(
                tenant_id=env["tenant_id"],
                contact_id=merged.id,
                kind=ContactMethodKind.PHONE.value,
                value="+911111111111",
                normalized_value="+911111111111",
            )
            s.add(merged_phone)
            s.flush()
            opp_s = service.open_opportunity(
                s, actor=actor, contact_id=survivor.id, project_id=env["project_id"]
            )
            opp_m = service.open_opportunity(
                s, actor=actor, contact_id=merged.id, project_id=env["project2_id"]
            )
            s.flush()

            merge = service.merge_contacts(
                s, actor=actor, survivor_id=survivor.id, merged_id=merged.id, reason="dup"
            )
            s.expunge_all()

            survivor = s.get(Contact, survivor.id)
            merged = s.get(Contact, merged.id)
            assert merged.status == ContactStatus.MERGED.value
            assert merged.merged_into_id == survivor.id
            moved = set(merge.evidence["moved_method_ids"])
            # both the resolve-created email method and the extra phone moved
            assert str(merged_phone.id) in moved
            assert len(moved) == 2
            # opportunities repointed
            assert s.get(Opportunity, opp_m.id).contact_id == survivor.id
            assert s.get(Opportunity, opp_s.id).contact_id == survivor.id

            # UNMERGE restores exactly
            service.unmerge_contacts(s, actor=actor, merge_id=merge.id)
            s.expunge_all()
            merged = s.get(Contact, merged.id)
            assert merged.status == ContactStatus.ACTIVE.value
            assert merged.merged_into_id is None
            assert s.get(Opportunity, opp_m.id).contact_id == merged.id
            restored_method = s.get(ContactMethod, merged_phone.id)
            assert restored_method.contact_id == merged.id

    def test_self_merge_refused(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="x@ex.com")
            with pytest.raises(MergeError):
                service.merge_contacts(
                    s, actor=actor, survivor_id=c.id, merged_id=c.id
                )


class TestConvertLead:
    def test_idempotent_from_same_lead(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            lead = Lead(
                tenant_id=env["tenant_id"],
                full_name="Buyer One",
                email="lead@ex.com",
                phone="+919812345678",
                project_id=env["project_id"],
                source=LeadSource.WEBSITE.value,
                status="NEW",
                consent_to_contact=True,
            )
            s.add(lead)
            s.flush()
            o1 = service.convert_lead(s, actor=actor, lead_id=lead.id)
            o2 = service.convert_lead(s, actor=actor, lead_id=lead.id)
            assert o1.id == o2.id
            assert o1.lead_id == lead.id
            assert o1.source == LeadSource.WEBSITE.value


class TestStageTransitions:
    def test_illegal_transition_409(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="st@ex.com")
            opp = service.open_opportunity(
                s, actor=actor, contact_id=c.id, project_id=env["project_id"]
            )
            with pytest.raises(InvalidStageTransitionError):
                service.update_opportunity(
                    s,
                    actor=actor,
                    opportunity_id=opp.id,
                    fields={"stage": OpportunityStage.WON},
                )

    def test_legal_transition(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="st2@ex.com")
            opp = service.open_opportunity(
                s, actor=actor, contact_id=c.id, project_id=env["project_id"]
            )
            updated = service.update_opportunity(
                s,
                actor=actor,
                opportunity_id=opp.id,
                fields={"stage": OpportunityStage.CONTACTED},
            )
            assert updated.stage == OpportunityStage.CONTACTED.value


class TestCreateContact:
    def test_create_applies_profile_and_provenance(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            contact, method, created = service.create_contact(
                s,
                actor=actor,
                display_name="Console",
                email="Console@Ex.com",
                phone="+91 96115 02119",
                primary_language="mr",
                notes="manual add",
            )
            assert created is True
            assert method.is_primary is True
            assert method.normalized_value == "console@ex.com"
            assert contact.display_name == "Console"
            assert contact.primary_language == "mr"
            assert contact.notes == "manual add"
            # uuid key stands: console methods are UNVERIFIED
            assert contact.canonical_key.startswith("uuid:")
            assert method.provenance["source"] == "admin_manual"
            assert method.provenance["method"] == "console"
            assert method.provenance["actor_user_id"] == str(actor.id)
            assert "captured_at" in method.provenance

    def test_repeat_submission_is_idempotent(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c1, m1, created1 = service.create_contact(
                s, actor=actor, display_name="One", email="one@ex.com"
            )
            c2, m2, created2 = service.create_contact(
                s, actor=actor, display_name="Ignored", email="ONE@EX.com"
            )
            assert created1 is True
            assert created2 is False
            assert c2.id == c1.id
            assert m2.id == m1.id
            # existing profile is NOT overwritten by the repeat call
            assert c2.display_name == "One"

    def test_phone_identity_matches_email_created_contact(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c1, _, created1 = service.create_contact(
                s, actor=actor, display_name="Dual",
                email="dual@ex.com", phone="+919876543210",
            )
            c2, m2, created2 = service.create_contact(
                s, actor=actor, display_name="Dual", phone="+91-98765-43210"
            )
            assert created1 is True and created2 is False
            assert c2.id == c1.id
            assert m2.kind == ContactMethodKind.PHONE.value

    def test_canonical_key_unchanged_on_repeat_after_verify(self, env) -> None:
        """Create-time recompute never fires on an idempotent repeat: a
        contact whose method later becomes VERIFIED keeps its original key
        until a MERGE-path recompute (documented CREATE-only rule)."""
        with env["factory"]() as s:
            actor = _actor(s, env)
            c1, m1, created1 = service.create_contact(
                s, actor=actor, display_name="Verified", email="v@ex.com"
            )
            assert created1 is True
            key_before = c1.canonical_key
            m1.verification_state = VerificationState.VERIFIED.value
            s.commit()
            c2, m2, created2 = service.create_contact(
                s, actor=actor, display_name="Dup", email="V@ex.com"
            )
            assert created2 is False
            assert c2.id == c1.id
            # repeat path performs NO canonical_key recompute
            assert c2.canonical_key == key_before


class TestUpdateContactService:
    def test_empty_fields_rejected_before_lookup(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="u1@ex.com")
            with pytest.raises(ContactUpdateError):
                service.update_contact(s, actor=actor, contact_id=c.id, fields={})

    def test_non_editable_fields_rejected(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="u2@ex.com")
            for fields in ({"status": "ACTIVE"}, {"merged_into_id": None}):
                with pytest.raises(ContactUpdateError):
                    service.update_contact(
                        s, actor=actor, contact_id=c.id, fields=fields
                    )

    def test_updates_only_allowed_fields(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c = _contact(s, env["tenant_id"], email="u3@ex.com")
            key_before = c.canonical_key
            updated = service.update_contact(
                s,
                actor=actor,
                contact_id=c.id,
                fields={"display_name": "Renamed", "notes": "n", "primary_language": "hi"},
            )
            assert updated.display_name == "Renamed"
            assert updated.notes == "n"
            assert updated.primary_language == "hi"
            assert updated.canonical_key == key_before

    def test_merged_contact_not_editable(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            survivor = _contact(s, env["tenant_id"], email="sv@ex.com")
            merged = _contact(s, env["tenant_id"], email="mg@ex.com")
            service.merge_contacts(
                s, actor=actor, survivor_id=survivor.id, merged_id=merged.id
            )
            with pytest.raises(ContactUpdateError):
                service.update_contact(
                    s, actor=actor, contact_id=merged.id, fields={"notes": "x"}
                )

    def test_buyer_cannot_patch_other_contact(self, env) -> None:
        with env["factory"]() as s:
            _actor(s, env)
            c = _contact(s, env["tenant_id"], email="u4@ex.com")
            buyer = create_user_with_role(
                s,
                full_name="Buyer",
                email=f"buy-{uuid4().hex[:6]}@ex.com",
                password=TEST_PASSWORD,
                role_name=RoleName.BUYER,
                tenant_id=env["tenant_id"],
            )
            s.commit()
            with pytest.raises(CustomerAccessDeniedError):
                service.update_contact(
                    s, actor=buyer, contact_id=c.id, fields={"notes": "x"}
                )

    def test_buyer_can_patch_own_contact(self, env) -> None:
        with env["factory"]() as s:
            c = _contact(s, env["tenant_id"], email="own-patch@ex.com")
            buyer = create_user_with_role(
                s,
                full_name="Buyer Own",
                email="own-patch@ex.com",
                password=TEST_PASSWORD,
                role_name=RoleName.BUYER,
                tenant_id=env["tenant_id"],
            )
            s.commit()
            updated = service.update_contact(
                s, actor=buyer, contact_id=c.id, fields={"notes": "self"}
            )
            assert updated.notes == "self"


class TestListMergesService:
    def test_newest_first_and_tenant_scoped(self, env) -> None:
        from datetime import UTC, datetime

        with env["factory"]() as s:
            actor = _actor(s, env)
            a1 = _contact(s, env["tenant_id"], email="la1@ex.com")
            b1 = _contact(s, env["tenant_id"], email="lb1@ex.com")
            m1 = service.merge_contacts(
                s, actor=actor, survivor_id=a1.id, merged_id=b1.id, reason="first"
            )
            a2 = _contact(s, env["tenant_id"], email="la2@ex.com")
            b2 = _contact(s, env["tenant_id"], email="lb2@ex.com")
            m2 = service.merge_contacts(
                s, actor=actor, survivor_id=a2.id, merged_id=b2.id, reason="second"
            )
            # Pin timestamps so "newest first" is deterministic: SQLite
            # CURRENT_TIMESTAMP has second precision and the id tie-breaker
            # is a random UUID.
            m1.created_at = datetime(2026, 1, 1, tzinfo=UTC)
            m2.created_at = datetime(2026, 1, 2, tzinfo=UTC)
            # other tenant merge must not leak
            other = Tenant(slug=f"om-{uuid4().hex[:6]}", name="OM")
            s.add(other)
            s.flush()
            o1 = Contact(
                tenant_id=other.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="O1",
            )
            o2 = Contact(
                tenant_id=other.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="O2",
            )
            s.add_all([o1, o2])
            s.flush()
            s.add(
                ContactMerge(
                    tenant_id=other.id,
                    survivor_id=o1.id,
                    merged_id=o2.id,
                    evidence={},
                )
            )
            s.commit()

            result = service.list_merges(s, actor=actor, limit=50, offset=0)
            assert result.total == 2
            assert [i.reason for i in result.items] == ["second", "first"]
            assert result.items[0].id == m2.id
            assert result.items[1].id == m1.id

            window = service.list_merges(s, actor=actor, limit=1, offset=1)
            assert window.total == 2
            assert window.limit == 1
            assert window.offset == 1
            assert [i.reason for i in window.items] == ["first"]


class TestListEnrichmentService:
    def test_counts_and_primary_method_via_grouped_queries(self, env) -> None:
        with env["factory"]() as s:
            actor = _actor(s, env)
            c1, _, _ = service.resolve_contact(
                s, tenant_id=env["tenant_id"], email="e1@ex.com", phone="+911000000001",
                display_name="E1",
            )
            c2, _, _ = service.resolve_contact(
                s, tenant_id=env["tenant_id"], phone="+911000000002", display_name="E2",
            )
            s.flush()
            service.open_opportunity(
                s, actor=actor, contact_id=c1.id, project_id=env["project_id"]
            )
            service.open_opportunity(
                s, actor=actor, contact_id=c1.id, project_id=env["project2_id"]
            )
            s.commit()

            result = service.list_contacts(s, actor=actor, page=1, page_size=20)
            by_id = {i.id: i for i in result.items}
            assert by_id[c1.id].opportunities_count == 2
            assert by_id[c1.id].primary_method is not None
            assert by_id[c1.id].primary_method.kind == ContactMethodKind.EMAIL
            assert by_id[c1.id].primary_method.value == "e1@ex.com"
            assert by_id[c2.id].opportunities_count == 0
            assert by_id[c2.id].primary_method.kind == ContactMethodKind.PHONE
            assert by_id[c2.id].primary_method.value == "+911000000002"

    def test_service_list_queries_are_bounded(self, env) -> None:
        """list_contacts must not fan out per-row: page fetch + 2 enrichment
        queries (+ count)."""
        from sqlalchemy import event

        with env["factory"]() as s:
            actor = _actor(s, env)
            for i in range(5):
                _contact(s, env["tenant_id"], email=f"bounded{i}@ex.com")
            engine = s.get_bind()
            counters = {"n": 0}

            def _count(*args, **kwargs):
                counters["n"] += 1

            event.listen(engine, "before_cursor_execute", _count)
            try:
                result = service.list_contacts(s, actor=actor, page=1, page_size=20)
            finally:
                event.remove(engine, "before_cursor_execute", _count)
            assert len(result.items) == 5
            # count + page + primary methods + opportunity counts = 4
            assert counters["n"] <= 4
