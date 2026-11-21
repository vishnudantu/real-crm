"""Domain errors for omnichannel messaging and calling."""

from __future__ import annotations


class ChannelError(Exception):
    """Base error for omnichannel operations."""


class ChannelConfigurationError(ChannelError):
    """A channel or provider is missing required configuration."""


class ChannelWebhookVerificationError(ChannelError):
    """A webhook failed signature or subscription verification."""


class ChannelMessageSendError(ChannelError):
    """An outbound provider rejected the message."""


class ChannelConversationNotFoundError(ChannelError):
    """No thread exists for the requested identifier within the tenant."""


class ChannelAccessDeniedError(ChannelError):
    """The caller lacks permission for the requested channel operation."""


class RecordingConsentRequiredError(ChannelError):
    """Recording cannot start without explicit disclosure to the contact."""
