"""Integration tests: channel ingestion, inbox, replies, and simulated calling.

Vault-dependent flows import ``cryptography`` transitively; those tests skip
until the dependency is installed so the suite remains meaningful either way.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip(
    "cryptography", reason="Channel credential vault requires the cryptography package."
)

from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.modules.auth.security import hash_password  # noqa: E402
from app.modules.leads.models import Lead, LeadSource, LeadStatus  # noqa: E402
from app.modules.omnichannel import repository, service  # noqa: E402
from app.modules.omnichannel.calling import end_call, join_call, start_call  # noqa: E402
from app.modules.omnichannel.exceptions import (  # noqa: E402
    RecordingConsentRequiredError,
)
from app.modules.omnichannel.models import (  # noqa: E402
    CallStatus,
    ChannelConversation,
    ChannelType,
    MessageDirection,
)
from app.modules.omnichannel.schemas import (  # noqa: E402
    CallStartRequest,
    ChannelCredentialUpsert,
)
from app.modules.projects.models import Project, ProjectStatus  # noqa: E402
from app.modules.tenancy.models import Tenant  # noqa: E402
from app.modules.users.models import Role, RoleName, User  # noqa: E402
from app.modules.omnichannel.webhooks import parse_meta_messages  # noqa: E402
from tests.support import TEST_PASSWORD  # noqa: E402


def _fixture(session: Session) -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"omni-{uuid4().hex[:8]}", name="Omni Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Omni Admin",
        email=f"admin.{tenant.id.hex[:10]}@omni.example",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()  # assign admin.id before referencing it in the project FK
    project = Project(
        tenant_id=tenant.id,
        name="Omni Tower",
        slug=f"omni-tower-{tenant.id.hex[:8]}",
        location="Hyderabad",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id,
        full_name="Known Buyer",
        email="known@omni.example",
        phone="919800000001",
        project_id=project.id,
        source=LeadSource.WEBSITE.value,
        status=LeadStatus.NEW.value,
        consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project


def _configure_simulated_channels(session: Session, admin: User) -> None:
    # Channel features default to OFF; the operator enables them explicitly.
    from app.modules.operator.feature_models import TenantFeature

    for feature_key in ("omnichannel_inbox", "channel_whatsapp", "calling"):
        session.add(
            TenantFeature(tenant_id=admin.tenant_id, feature=feature_key, enabled=True)
        )
    session.commit()
    for channel, config in (
        (ChannelType.WHATSAPP, {"allow_unsigned_simulation": True}),
        (ChannelType.VOICE, {"ws_url": None}),
    ):
        service.upsert_credential(
            session,
            actor=admin,
            payload=ChannelCredentialUpsert(
                channel=channel,
                provider="simulated",
                credentials={"note": "test only"},
                config=config,
            ),
        )


def _whatsapp_events(mid: str, phone: str, text: str = "Site visit tomorrow?"):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"wa_id": phone, "profile": {"name": "Asha R"}}],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": mid,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }
    return parse_meta_messages(payload, ChannelType.WHATSAPP.value)


@pytest.fixture(autouse=True)
def _dev_vault_key() -> None:
    """Provide a development Fernet key so the tenant credential vault runs."""

    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    get_settings().encryption_key = Fernet.generate_key().decode()


class TestInboundIngestion:
    def test_inbound_links_known_phone_to_existing_lead(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            event = _whatsapp_events("wamid.T1", "919800000001")[0]
            message = service.ingest_inbound(session, tenant_id=tenant.id, event=event)
            conversation = session.get(ChannelConversation, message.conversation_id)
            assert conversation is not None
            existing_lead = session.query(Lead).filter_by(phone="919800000001").one()
            assert conversation.lead_id == existing_lead.id
            assert conversation.unread_count == 1
            assert conversation.contact_name == "Asha R"
            assert message.direction == MessageDirection.INBOUND.value

    def test_duplicate_webhook_delivery_is_idempotent(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            event = _whatsapp_events("wamid.DUP", "919800000001")[0]
            first = service.ingest_inbound(session, tenant_id=tenant.id, event=event)
            second = service.ingest_inbound(session, tenant_id=tenant.id, event=event)
            assert first.id == second.id

    def test_unknown_number_creates_lead_without_marketing_consent(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            event = _whatsapp_events("wamid.NEW", "919777777777")[0]
            message = service.ingest_inbound(session, tenant_id=tenant.id, event=event)
            conversation = session.get(ChannelConversation, message.conversation_id)
            new_lead = session.get(Lead, conversation.lead_id)
            assert new_lead is not None
            assert new_lead.phone == "919777777777"
            # DPDP: an inbound enquiry alone is not marketing consent.
            assert new_lead.consent_to_contact is False


class TestOutboundReplies:
    def test_simulated_reply_marks_sent_with_external_id(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            event = _whatsapp_events("wamid.R1", "919800000001")[0]
            inbound = service.ingest_inbound(session, tenant_id=tenant.id, event=event)
            reply = service.send_reply(
                session,
                actor=admin,
                conversation_id=inbound.conversation_id,
                text="Yes, 10 AM Saturday works.",
            )
            assert reply.direction == MessageDirection.OUTBOUND.value
            assert reply.status == "SENT"
            assert reply.external_message_id is not None
            conversation = session.get(ChannelConversation, inbound.conversation_id)
            assert conversation.unread_count == 0
            assert conversation.last_message_preview == "Yes, 10 AM Saturday works."


class TestCalling:
    def test_call_lifecycle_with_simulated_provider(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            call, token, connection = start_call(
                session,
                actor=admin,
                payload=CallStartRequest(destination="919800000001", record=False),
            )
            assert call.status == CallStatus.INITIATED.value
            assert token
            assert connection["mode"] == "simulated"
            joined_call, join_token, _ = join_call(
                session, actor=admin, call_id=call.id, display_name="Admin"
            )
            assert joined_call.status == CallStatus.IN_PROGRESS.value
            assert join_token
            finished = end_call(session, actor=admin, call_id=call.id)
            assert finished.status == CallStatus.COMPLETED.value

    def test_recording_requires_consent_confirmation(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            with pytest.raises(RecordingConsentRequiredError):
                start_call(
                    session,
                    actor=admin,
                    payload=CallStartRequest(destination="919800000001", record=True),
                )


class TestCrossTenantIsolation:
    def test_other_tenant_cannot_read_inbox(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant, admin, _project = _fixture(session)
            _configure_simulated_channels(session, admin)
            event = _whatsapp_events("wamid.ISO", "919800000001")[0]
            service.ingest_inbound(session, tenant_id=tenant.id, event=event)

            other_tenant, other_admin, _ = _fixture(session)
            items, total, _ = repository.list_inbox(session, tenant_id=other_tenant.id)
            assert total == 0 and items == []
            with pytest.raises(Exception):
                # The other tenant's admin cannot act on tenant one's thread.
                service.send_reply(
                    session,
                    actor=other_admin,
                    conversation_id=repository.list_inbox(session, tenant_id=tenant.id)[0][0].id,
                    text="sneak",
                )
