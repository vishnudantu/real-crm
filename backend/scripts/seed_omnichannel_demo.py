"""Seed an omnichannel demo tenant, admin, project, and feature flags (idempotent).

Run from the backend directory:  python scripts/seed_omnichannel_demo.py
"""

import os
import secrets
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.modules.auth.security import hash_password  # noqa: E402
from app.modules.leads.models import Lead, LeadSource, LeadStatus  # noqa: E402
from app.modules.omnichannel.models import (  # noqa: E402
    ChannelConversation,
    ChannelMessage,
    ChannelType,
    MessageDirection,
)
from app.modules.operator.feature_models import TenantFeature  # noqa: E402
from app.modules.projects.models import Project, ProjectStatus  # noqa: E402
from app.modules.tenancy.models import Tenant  # noqa: E402
from app.modules.users.models import Role, RoleName, User  # noqa: E402

settings = get_settings()
db_url = settings.database_url.get_secret_value()
if not db_url.startswith("sqlite"):
    print("This demo seed targets the local SQLite dev DB only. Set DATABASE_URL accordingly.")
    sys.exit(2)

engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)

DEMO_ADMIN_PASSWORD = "DemoAdmin@2026"
DEMO_SALES_PASSWORD = "DemoSales@2026"


def upsert_feature(session, tenant_id, key, enabled=True):
    row = session.scalar(
        select(TenantFeature).where(
            TenantFeature.tenant_id == tenant_id, TenantFeature.feature == key
        )
    )
    if row is None:
        row = TenantFeature(tenant_id=tenant_id, feature=key)
        session.add(row)
    row.enabled = enabled
    row.reason = "Demo tenant seed"
    row.set_by_email = "demo-seed"


def main() -> int:
    with SessionLocal() as db:
        # 1. Tenant
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "omni-demo"))
        if tenant is None:
            tenant = Tenant(
                slug="omni-demo",
                name="Skyline Developers",
                brand_name="Skyline Developers",
                theme_json={
                    "brand_name": "Skyline Developers",
                    "primary_color": "#2563eb",
                    "welcome_message": "Namaste! Ask us about Skyline Residency.",
                },
            )
            db.add(tenant)
            db.flush()
            print("Created tenant: Skyline Developers (omni-demo)")
        else:
            print("Tenant omni-demo already exists; updating in place.")

        # 2. Features enabled for the demo
        for key in (
            "omnichannel_inbox",
            "channel_whatsapp",
            "channel_instagram",
            "channel_messenger",
            "calling",
            "web_widget",
            "post_sales",
            "connectors",
            "analytics",
        ):
            upsert_feature(db, tenant.id, key, True)

        # 3. Admin + sales user
        admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
        sales_role = db.scalar(select(Role).where(Role.name == RoleName.SALES_EXECUTIVE.value))
        if admin_role is None or sales_role is None:
            from app.modules.users.service import seed_roles

            seed_roles(db)
            admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
            sales_role = db.scalar(select(Role).where(Role.name == RoleName.SALES_EXECUTIVE.value))

        admin = db.scalar(select(User).where(User.email == "admin@skyline-demo.example"))
        if admin is None:
            admin = User(
                tenant_id=tenant.id,
                full_name="Demo Admin",
                email="admin@skyline-demo.example",
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                role_id=admin_role.id,
                is_active=True,
            )
            db.add(admin)
        else:
            admin.password_hash = hash_password(DEMO_ADMIN_PASSWORD)
            admin.is_active = True
        sales = db.scalar(select(User).where(User.email == "sales@skyline-demo.example"))
        if sales is None:
            sales = User(
                tenant_id=tenant.id,
                full_name="Demo Sales Executive",
                email="sales@skyline-demo.example",
                password_hash=hash_password(DEMO_SALES_PASSWORD),
                role_id=sales_role.id,
                is_active=True,
            )
            db.add(sales)
        db.flush()

        # 4. Active project
        project = db.scalar(select(Project).where(Project.tenant_id == tenant.id))
        if project is None:
            project = Project(
                tenant_id=tenant.id,
                name="Skyline Residency",
                slug=f"skyline-residency-{tenant.id.hex[:8]}",
                location="Hyderabad",
                status=ProjectStatus.ACTIVE.value,
                created_by=admin.id,
                rera_number="PR/TG/HYDERABAD/2024/DEMO001",
            )
            db.add(project)
            db.flush()
        else:
            project.status = ProjectStatus.ACTIVE.value

        # 5. Sample WhatsApp lead + conversation so the inbox has content
        lead = db.scalar(
            select(Lead).where(
                Lead.tenant_id == tenant.id, Lead.phone == "919811112222"
            )
        )
        if lead is None:
            lead = Lead(
                tenant_id=tenant.id,
                full_name="Aarav Mehta",
                phone="919811112222",
                email="aarav@example.com",
                project_id=project.id,
                source=LeadSource.WHATSAPP.value if hasattr(LeadSource, "WHATSAPP") else LeadSource.SOCIAL_MEDIA.value,
                status=LeadStatus.NEW.value,
                consent_to_contact=True,
            )
            db.add(lead)
            db.flush()

        conversation = db.scalar(
            select(ChannelConversation).where(
                ChannelConversation.tenant_id == tenant.id,
                ChannelConversation.external_thread_id == "919811112222",
                ChannelConversation.channel == ChannelType.WHATSAPP.value,
            )
        )
        if conversation is None:
            conversation = ChannelConversation(
                tenant_id=tenant.id,
                lead_id=lead.id,
                channel=ChannelType.WHATSAPP.value,
                external_thread_id="919811112222",
                contact_name="Aarav Mehta",
                contact_handle="919811112222",
                unread_count=2,
            )
            db.add(conversation)
            db.flush()
            samples = [
                (MessageDirection.INBOUND.value, "Hi, is the 3BHK in Skyline Residency still available?"),
                (MessageDirection.OUTBOUND.value, "Namaste Aarav! Yes, 3BHK units are available. Would you like the floor plan?"),
                (MessageDirection.INBOUND.value, "Yes please, and what's the price for the 12th floor?"),
            ]
            for direction, text in samples:
                db.add(
                    ChannelMessage(
                        tenant_id=tenant.id,
                        conversation_id=conversation.id,
                        channel=ChannelType.WHATSAPP.value,
                        direction=direction,
                        content=text,
                        content_type="TEXT",
                        status="SENT" if direction == MessageDirection.OUTBOUND.value else "RECEIVED",
                    )
                )
            conversation.last_message_preview = samples[-1][1][:500]

        db.commit()

    print("\nDEMO READY")
    print("  Tenant slug:      omni-demo")
    print("  Brand:            Skyline Developers")
    print(f"  Admin login:      admin@skyline-demo.example / {DEMO_ADMIN_PASSWORD}")
    print(f"  Sales login:      sales@skyline-demo.example / {DEMO_SALES_PASSWORD}")
    print(f"  Widget embed URL: http://127.0.0.1:8010/api/v1/widget/omni-demo/embed.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
