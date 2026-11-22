"""Unit tests for the customer + opportunity graph service (PF-008/009)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.service import create_user_with_role
from app.modules.customers import service
from app.modules.customers.exceptions import (
    InvalidStageTransitionError,
    MergeError,
)
from app.modules.customers.models import (
    Contact,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    Opportunity,
    OpportunityStage,
    VerificationState,
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
