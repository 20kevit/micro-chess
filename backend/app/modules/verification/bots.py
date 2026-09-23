"""Bot provider adapters (Telegram / Bale).

Domain code never imports a vendor SDK and never sees a bot token:
tokens come only from the environment inside these adapters. Both
providers share the same JSON wire shape (Bale's Bot API is
Telegram-compatible at ``tapi.bale.ai``), so one implementation serves
both with a different base URL. Reply failures never raise — a user
that cannot be messaged must still be verifiable; delivery problems
are reported as ``False``.

FakeBotAdapter is the test seam (outbox inspection, scripted
``get_me``), injected via ``set_adapter``.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger("microchess.verification")


@dataclass(frozen=True)
class BotResult:
    ok: bool
    error: str = ""


class BotAdapter:
    """One messaging provider (send-only surface used by verification)."""

    channel: str = ""

    def send_text(self, chat_id: str, text: str,
                  reply_markup: dict | None = None) -> BotResult:
        raise NotImplementedError

    def get_me(self) -> dict | None:
        raise NotImplementedError


def _post_json(url: str, payload: dict, timeout_s: float = 10.0) -> tuple[int, bytes]:
    import json as _json

    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        status = getattr(resp, "status", 200)
        raw = resp.read()
    return int(status), raw if isinstance(raw, bytes) else b""


class HttpBotAdapter(BotAdapter):
    """Telegram-compatible HTTP adapter (Telegram + Bale)."""

    def __init__(self, *, channel: str, base_url: str, token: str,
                 timeout_s: float = 10.0) -> None:
        self.channel = channel
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_s = timeout_s

    def _call(self, method: str, payload: dict) -> dict | None:
        import json as _json

        if not self._token:
            return None
        try:
            status, raw = _post_json(
                f"{self._base_url}/bot{self._token}/{method}", payload, self._timeout_s
            )
            if status != 200:
                return None
            body = _json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict) or body.get("ok") is not True:
                return None
            result = body.get("result")
            return result if isinstance(result, dict) else {}
        except Exception:  # noqa: BLE001 - provider failures stay local
            logger.warning("%s bot call failed: %s", self.channel, method)
            return None

    def send_text(self, chat_id: str, text: str,
                  reply_markup: dict | None = None) -> BotResult:
        payload: dict = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        outcome = self._call("sendMessage", payload)
        return BotResult(ok=outcome is not None,
                         error="" if outcome is not None else "send_failed")

    def get_me(self) -> dict | None:
        return self._call("getMe", {})


class FakeBotAdapter(BotAdapter):
    """Test seam: records sends, scripted get_me, never touches network."""

    def __init__(self, *, channel: str, me: dict | None = None) -> None:
        self.channel = channel
        self._me = {"id": 1, "username": f"test_{channel}_bot"} if me is None else me
        self.outbox: list[dict] = []

    def send_text(self, chat_id: str, text: str,
                  reply_markup: dict | None = None) -> BotResult:
        self.outbox.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return BotResult(ok=True)

    def get_me(self) -> dict | None:
        return dict(self._me)

    def clear(self) -> None:
        self.outbox.clear()


def _adapter_for(channel: str) -> BotAdapter:
    channel = (channel or "").strip().lower()
    if channel == "telegram":
        return HttpBotAdapter(
            channel="telegram",
            base_url="https://api.telegram.org",
            token=os.environ.get("TELEGRAM_BOT_TOKEN") or "",
        )
    if channel == "bale":
        return HttpBotAdapter(
            channel="bale",
            base_url="https://tapi.bale.ai",
            token=os.environ.get("BALE_BOT_TOKEN") or "",
        )
    raise ValueError("unknown_channel")


_overrides: dict[str, BotAdapter] = {}


def set_adapter(adapter: BotAdapter) -> None:
    """Inject a test adapter for one channel (tests only)."""
    _overrides[adapter.channel] = adapter


def clear_adapters() -> None:
    _overrides.clear()


def get_adapter(channel: str) -> BotAdapter:
    channel = (channel or "").strip().lower()
    if channel in _overrides:
        return _overrides[channel]
    return _adapter_for(channel)


def bot_username(channel: str) -> str:
    channel = (channel or "").strip().lower()
    if channel == "telegram":
        return os.environ.get("TELEGRAM_BOT_USERNAME") or ""
    if channel == "bale":
        return os.environ.get("BALE_BOT_USERNAME") or ""
    return ""


def bot_url(channel: str) -> str:
    """Public bot address without any secret (deep link carries no token)."""
    name = bot_username(channel)
    if not name:
        return ""
    if channel == "telegram":
        return f"https://t.me/{name}"
    if channel == "bale":
        return f"https://ble.ir/{name}"
    return ""


def share_keyboard(label: str) -> dict:
    """Official contact-sharing keyboard (Telegram + Bale compatible)."""
    return {
        "keyboard": [[{"text": label, "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def remove_keyboard() -> dict:
    return {"remove_keyboard": True}


# --- Persian bot copy (concise, no internal ids/tokens) ----------------------

def msg_welcome(channel_name: str) -> str:
    return (
        f"به ربات احراز میکروچس خوش آمدی.\n"
        f"کد ۶ رقمی نمایش‌داده‌شده در میکروچس را همین‌جا بفرست "
        f"تا حسابت را پیدا کنم."
    )


def msg_ask_contact() -> str:
    return (
        "حسابت پیدا شد.\n"
        "حالا دکمه «اشتراک شماره» را بزن تا شماره‌ات را رسماً بفرستی.\n"
        "شماره تلفن تو فقط برای احراز حساب استفاده می‌شود."
    )


def msg_success() -> str:
    return "شمارت تأیید شد. برگرد به میکروچس و ادامه بده."


def msg_failed() -> str:
    return (
        "این اطلاعات قابل تأیید نیست. دوباره تلاش کن یا از میکروچس "
        "یک کد تازه بگیر."
    )


def msg_expired() -> str:
    return "این کد منقضی شده. از میکروچس یک کد تازه بگیر و دوباره بفرست."


def msg_unknown() -> str:
    return "متوجه نشدم. اول کد ۶ رقمی میکروچس را بفرست."


SHARE_BUTTON_LABEL = "اشتراک شماره"
