"""Resolve channel and calling adapters without leaking provider details."""

from __future__ import annotations

from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.models import ChannelType
from app.modules.omnichannel.providers.livekit import LiveKitCallProvider
from app.modules.omnichannel.providers.meta import (
    InstagramProvider,
    MessengerProvider,
    WhatsAppCloudProvider,
)
from app.modules.omnichannel.providers.simulated import SimulatedCallProvider, SimulatedMessageProvider


def build_message_provider(channel: str, provider_name: str):
    """Return the outbound adapter for a channel's configured provider."""

    if provider_name == "simulated":
        return SimulatedMessageProvider()
    if channel == ChannelType.WHATSAPP.value and provider_name == "meta":
        return WhatsAppCloudProvider()
    if channel == ChannelType.MESSENGER.value and provider_name == "meta":
        return MessengerProvider()
    if channel == ChannelType.INSTAGRAM.value and provider_name == "meta":
        return InstagramProvider()
    raise ChannelConfigurationError(
        f"No outbound adapter for channel={channel} provider={provider_name}."
    )


def build_call_provider(provider_name: str):
    if provider_name == "simulated":
        return SimulatedCallProvider()
    if provider_name == "livekit":
        return LiveKitCallProvider()
    raise ChannelConfigurationError(f"Unsupported call provider: {provider_name}.")
