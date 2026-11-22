"""API v1 router composition."""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.ai_assistant.router import router as ai_assistant_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.bookings.router import bookings_router, slots_router
from app.modules.brokers.router import router as brokers_router
from app.modules.connectors.router import router as connectors_router
from app.modules.conversations.router import router as conversations_router
from app.modules.customers.router import opportunities_router, router as customers_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.documents.router import router as documents_router
from app.modules.follow_ups.router import router as follow_ups_router
from app.modules.handoffs.router import handoffs_router
from app.modules.integrations.connections_router import router as integration_connections_router
from app.modules.integrations.router import router as integrations_router
from app.modules.inventory.router import router as inventory_router
from app.modules.leads.router import router as leads_router
from app.modules.messages.router import router as messages_router
from app.modules.messaging.router import router as messaging_router
from app.modules.notifications.router import notifications_router
from app.modules.omnichannel.router import router as omnichannel_router
from app.modules.omnichannel.router import webhook_router as channel_webhook_router
from app.modules.omnichannel.widget_router import widget_router
from app.modules.postsales.router import router as postsales_router
from app.modules.operator.router import router as operator_router
from app.modules.projects.router import router as projects_router
from app.modules.settings.router import settings_router
from app.modules.tenancy.router import router as tenancy_router
from app.modules.teamchat.router import router as teamchat_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(projects_router)
api_router.include_router(leads_router)
api_router.include_router(conversations_router)
api_router.include_router(customers_router)
api_router.include_router(opportunities_router)
api_router.include_router(messages_router)
api_router.include_router(ai_assistant_router)
api_router.include_router(slots_router)
api_router.include_router(bookings_router)
api_router.include_router(brokers_router)
api_router.include_router(follow_ups_router)
api_router.include_router(handoffs_router)
api_router.include_router(notifications_router)
api_router.include_router(dashboard_router)
api_router.include_router(settings_router)
api_router.include_router(tenancy_router)
api_router.include_router(messaging_router)
api_router.include_router(operator_router)
api_router.include_router(connectors_router)
api_router.include_router(integration_connections_router)
api_router.include_router(integrations_router)
api_router.include_router(inventory_router)
api_router.include_router(billing_router)
api_router.include_router(postsales_router)
api_router.include_router(documents_router)
api_router.include_router(teamchat_router)
api_router.include_router(omnichannel_router)
api_router.include_router(channel_webhook_router)
api_router.include_router(widget_router)
