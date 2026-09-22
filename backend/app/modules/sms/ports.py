"""SMS provider abstraction (P11).

Domain code never imports a vendor SDK. The phone verification service
depends only on ``SmsProvider``; configuration selects the concrete
implementation. A test provider works without real SMS; the production
adapter reads credentials from the environment and fails safely.
"""

from __future__ import annotations

import logging
import os
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger("microchess.sms")


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    error: str = ""
    provider_message_id: str = ""


class SmsProvider:
    name: str = ""

    def send_otp(self, *, to: str, text: str) -> SmsResult:
        raise NotImplementedError


class TestSmsProvider(SmsProvider):
    """Development/test provider: never sends real SMS, records outbox."""

    name = "test"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.outbox: list[dict[str, str]] = []

    def send_otp(self, *, to: str, text: str) -> SmsResult:
        with self._lock:
            self.outbox.append({"to": to, "text": text})
        return SmsResult(ok=True, provider_message_id="test")

    def clear(self) -> None:
        with self._lock:
            self.outbox.clear()


class KavenegarProvider(SmsProvider):
    """Kavenegar SMS adapter (practical low-cost Iran-oriented choice).

    Uses the ``SendSimple`` HTTPS API with plain stdlib urllib (no new
    dependency). Credentials come only from the environment; the message
    text carries the OTP rendered by the caller (a plain Persian message,
    no template id required). Lookup/template sending is intentionally
    not required so deployment works with a basic API key + sender line.
    """

    name = "kavenegar"

    def __init__(self, *, api_key: str, sender: str, timeout_s: float = 10.0) -> None:
        self._api_key = api_key
        self._sender = sender
        self._timeout_s = timeout_s

    def send_otp(self, *, to: str, text: str) -> SmsResult:
        try:
            url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(self._api_key, safe='')}/sms/send.json"
            payload = urllib.parse.urlencode(
                {"receptor": to, "sender": self._sender, "message": text}
            ).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                status = getattr(resp, "status", 200)
            if status != 200:
                return SmsResult(ok=False, error=f"http_{status}")
            return SmsResult(ok=True)
        except Exception as exc:  # noqa: BLE001 - provider must fail safely
            logger.warning("kavenegar send failed: %s", type(exc).__name__)
            return SmsResult(ok=False, error="provider_error")


_test_provider = TestSmsProvider()


def get_provider() -> SmsProvider:
    """Select the SMS provider from the environment (default: test)."""
    name = (os.environ.get("SMS_PROVIDER") or "test").strip().lower()
    if name == "kavenegar":
        api_key = os.environ.get("SMS_KAVENEGAR_API_KEY") or ""
        sender = os.environ.get("SMS_KAVENEGAR_SENDER") or ""
        if not api_key or not sender:
            logger.warning("kavenegar configured without credentials; OTP sends will fail safely")
            return KavenegarProvider(api_key="", sender="")
        return KavenegarProvider(api_key=api_key, sender=sender)
    return _test_provider


def test_provider() -> TestSmsProvider:
    return _test_provider


def provider_health() -> dict[str, object]:
    """Admin-safe health without exposing secrets (configured or not)."""
    name = (os.environ.get("SMS_PROVIDER") or "test").strip().lower()
    if name == "kavenegar":
        configured = bool(os.environ.get("SMS_KAVENEGAR_API_KEY")) and bool(
            os.environ.get("SMS_KAVENEGAR_SENDER")
        )
        return {"provider": "kavenegar", "configured": configured}
    return {"provider": "test", "configured": True}
