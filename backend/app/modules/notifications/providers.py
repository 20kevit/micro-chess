"""Delivery provider abstraction (Phase 11).

The notification domain never imports a vendor SDK. Each channel is a
small provider behind this interface; future EMAIL/PUSH/TELEGRAM channels
register here without changing domain events, decisions, or persistence.
Only ``in_app`` is registered today (see the Phase 11 specification:
external providers are optional and added only when required).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryOutcome:
    """Provider-independent delivery result (never carries payloads)."""

    delivered: bool
    # Short machine-readable error summary for ``last_error`` logging.
    error: str = ""


class NotificationProvider:
    """One delivery channel. Implementations must be side-effect scoped
    to their channel and must never raise for expected failures."""

    name: str = ""

    def send(self, notification) -> DeliveryOutcome:
        raise NotImplementedError


class InAppProvider(NotificationProvider):
    """In-app delivery: the notification row itself is the presentation.

    Persisting the row IS the delivery, so sending always succeeds. It
    still flows through a provider so status, retry, and logging stay
    uniform with future channels.
    """

    name = "in_app"

    def send(self, notification) -> DeliveryOutcome:
        _ = notification
        return DeliveryOutcome(delivered=True)


_PROVIDERS: dict[str, NotificationProvider] = {InAppProvider().name: InAppProvider()}


class _ExternalStubProvider(NotificationProvider):
    """P11 external channels (web_push/telegram/bale/sms).

    Dev-safe default: records the delivery decision without requiring
    vendor credentials. Real fan-out (bot API calls, SMS sends, push
    encryption) lives in the notify service which owns subscriptions,
    links, preferences, and rate limits; this stub keeps ``emit_event``
    vocabulary open for the new channels without coupling the
    notification domain to any SDK.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, notification) -> DeliveryOutcome:
        _ = notification
        return DeliveryOutcome(delivered=True)


for _channel in ("web_push", "telegram", "bale", "sms"):
    _PROVIDERS[_channel] = _ExternalStubProvider(_channel)


def register_provider(provider: NotificationProvider) -> None:
    """Register (or replace) a channel provider. Used by future channels
    and by tests injecting stub providers (provider isolation)."""
    _PROVIDERS[provider.name] = provider


def unregister_provider(name: str) -> None:
    _PROVIDERS.pop(name, None)


def get_provider(channel: str) -> NotificationProvider | None:
    return _PROVIDERS.get(channel)


def available_channels() -> list[str]:
    return sorted(_PROVIDERS.keys())
