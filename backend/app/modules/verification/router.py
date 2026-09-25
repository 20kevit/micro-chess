"""Verification routes: thin wiring over the verification service.

Owner endpoints are capability-guarded and user-scoped. The bot
webhook is provider-authenticated (shared secret, plus Telegram's
per-bot secret token where configured), idempotent, and never leaks
sensitive data: unknown or malformed updates answer 200 with no body
(the provider retries non-200s, and errors must not reveal state).
"""

import logging
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.core.rate_limit import enforce_verification_rate_limit, enforce_webhook_rate_limit
from app.modules.users.models import User
from app.modules.verification import bots, schemas, service

logger = logging.getLogger("microchess.verification")

router = APIRouter(tags=["verification"])

_PAIRING_RE = re.compile(r"^\d{6}$")


def _webhook_authorized(request: Request, path_secret: str | None = None) -> bool:
    shared = os.environ.get("BOT_WEBHOOK_SECRET") or ""
    if shared and (request.headers.get("x-bot-secret") or "") == shared:
        return True
    # Telegram's per-bot secret_token (set via setWebhook) arrives here.
    per_bot = os.environ.get("TELEGRAM_WEBHOOK_SECRET") or ""
    if per_bot and (request.headers.get("x-telegram-bot-api-secret-token") or "") == per_bot:
        return True
    # Bale cannot send custom headers: the operator registers the
    # webhook URL with an unguessable path secret instead
    # (/verification/webhook/<channel>/<secret>). This URL is
    # operator-configured only (setWebhook call), never shown to users,
    # never in the frontend, and excluded from access logs at the edge.
    if shared and path_secret and secrets_compare(path_secret, shared):
        return True
    return False


def secrets_compare(a: str, b: str) -> bool:
    import secrets as _secrets

    try:
        return _secrets.compare_digest(a, b)
    except Exception:
        return False


@router.post("/me/verification/sessions", response_model=schemas.SessionOut)
def create_session(
    body: schemas.SessionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
    _limited: None = Depends(enforce_verification_rate_limit),
):
    try:
        return service.create_session(db, user, body.channel)
    except ValueError as exc:
        code = str(exc)
        if code == "already_verified":
            raise HTTPException(status_code=409, detail=code)
        raise HTTPException(status_code=422, detail=code)


@router.get("/me/verification/status", response_model=schemas.VerificationStatusOut)
def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.verification_state(db, user)


def _chat_id_of(message: dict) -> str:
    chat = message.get("chat") or {}
    chat_id = chat.get("id", "")
    return str(chat_id).strip()[:100]


def _handle_update(db: Session, channel: str, update: dict) -> None:
    """Process one provider update (Telegram-compatible shape)."""
    if not isinstance(update, dict):
        return
    message = update.get("message") or {}
    if not isinstance(message, dict):
        return
    chat_id = _chat_id_of(message)
    if not chat_id:
        return
    adapter = bots.get_adapter(channel)
    sender = message.get("from") or {}
    sender_id = str(sender.get("id", "") or "").strip()
    text = message.get("text")
    if isinstance(text, str) and text.strip().startswith("/start"):
        adapter.send_text(chat_id, bots.msg_welcome(channel))
        return
    if isinstance(text, str) and _PAIRING_RE.match(text.strip()):
        try:
            service.claim_with_code(db, channel=channel,
                                    pairing_code=text.strip(), chat_id=chat_id)
        except ValueError as exc:
            code = str(exc)
            if code == "session_expired":
                adapter.send_text(chat_id, bots.msg_expired())
            else:
                adapter.send_text(chat_id, bots.msg_unknown())
            return
        adapter.send_text(chat_id, bots.msg_ask_contact(),
                          reply_markup=bots.share_keyboard(bots.SHARE_BUTTON_LABEL))
        return
    contact = message.get("contact")
    if isinstance(contact, dict):
        contact_user_id = str(contact.get("user_id", "") or "").strip()
        phone = str(contact.get("phone_number", "") or "")
        first_name = str(contact.get("first_name", "") or "")
        try:
            service.consume_with_contact(
                db, channel=channel, chat_id=chat_id, sender_id=sender_id,
                contact_user_id=contact_user_id, phone_raw=phone,
                display_name=first_name,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "session_expired":
                adapter.send_text(chat_id, bots.msg_expired(),
                                  reply_markup=bots.remove_keyboard())
            elif code == "phone_taken":
                # Generic: never reveal the other account.
                adapter.send_text(
                    chat_id,
                    "این شماره قبلاً برای یک حساب دیگر تأیید شده است.",
                    reply_markup=bots.remove_keyboard(),
                )
            else:
                adapter.send_text(chat_id, bots.msg_failed(),
                                  reply_markup=bots.remove_keyboard())
            return
        adapter.send_text(chat_id, bots.msg_success(),
                          reply_markup=bots.remove_keyboard())
        return
    adapter.send_text(chat_id, bots.msg_unknown())


@router.post("/verification/webhook/{channel}")
async def bot_webhook(channel: str, request: Request, db: Session = Depends(get_db),
                      _limited: None = Depends(enforce_webhook_rate_limit)):
    return await _bot_webhook_impl(channel=channel, request=request, db=db, path_secret=None)


@router.post("/verification/webhook/{channel}/{path_secret}")
async def bot_webhook_secret(channel: str, path_secret: str, request: Request,
                             db: Session = Depends(get_db),
                             _limited: None = Depends(enforce_webhook_rate_limit)):
    return await _bot_webhook_impl(channel=channel, request=request, db=db,
                                   path_secret=path_secret)


async def _bot_webhook_impl(channel: str, request: Request, db: Session,
                            path_secret: str | None):
    channel = (channel or "").strip().lower()
    if channel not in service.CHANNELS:
        raise HTTPException(status_code=404, detail="unknown_channel")
    if not _webhook_authorized(request, path_secret):
        raise HTTPException(status_code=403, detail="forbidden")
    if channel not in service.available_channels():
        return {"ok": True}
    try:
        update = await request.json()
    except Exception:
        update = {}
    if not isinstance(update, dict):
        update = {}
    try:
        _handle_update(db, channel, update)
    except Exception:  # noqa: BLE001 - webhook must never 500 on provider data
        logger.exception("verification webhook failed (channel=%s)", channel)
    return {"ok": True}
