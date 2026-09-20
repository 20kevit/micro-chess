"""Payment provider boundary.

The commerce flow depends only on the ``PaymentProvider`` protocol below;
vendor SDKs must never be imported into services, routers, or models
(same rule as ``audio/ports.py``). Today the configured provider is
``none``: ``NullProvider`` records intent but can never verify payment,
so no paid access can arise from it. Adding a real gateway later means
implementing this protocol + webhook verification, without touching
subscription/entitlement logic.
"""

from typing import Any, Protocol


class PaymentError(Exception):
    pass


class PaymentProvider(Protocol):
    """Vendor-neutral payment surface used by the billing service."""

    code: str

    def create_intent(
        self, *, amount_minor: int, currency: str, idempotency_key: str, metadata: dict
    ) -> dict:
        """Create a provider-side payment intent/order. Returns provider data."""
        ...

    def verify_callback(self, *, payload: bytes, signature: str | None) -> dict:
        """Verify a provider callback/webhook server-to-server.

        Returns ``{"provider_ref": str, "status": str, "amount_minor": int}``.
        Must raise on any verification failure; the caller never trusts
        browser claims (``POST /payment/success`` proves nothing).
        """
        ...


class NullProvider:
    """Placeholder provider: payment integration is not configured.

    ``create_intent`` always fails closed so checkout cannot proceed;
    ``verify_callback`` always fails so no subscription can activate.
    """

    code = "none"

    def create_intent(self, **_kwargs: Any) -> dict:
        raise PaymentError("payment_provider_not_configured")

    def verify_callback(self, **_kwargs: Any) -> dict:
        raise PaymentError("payment_provider_not_configured")


def get_provider(code: str | None = None) -> PaymentProvider:
    """Resolve the configured provider. Only ``none`` exists today."""
    _ = code
    return NullProvider()
