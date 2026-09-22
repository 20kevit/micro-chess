"""Notify routes: thin wiring (push, channel links, prefs, reminders, analytics)."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.notify import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["notify"])


@router.get("/me/push/subscriptions", response_model=list[schemas.PushSubscriptionOut])
def list_push(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_push(db, user.id)


@router.post("/me/push/subscriptions", response_model=schemas.PushSubscriptionOut)
def subscribe_push(
    body: schemas.PushSubscribeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        out = service.subscribe_push(db, user.id, endpoint=body.endpoint,
                                     p256dh=body.p256dh, auth=body.auth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"endpoint": out["endpoint"], "created_at": None}


@router.delete("/me/push/subscriptions", status_code=204)
def unsubscribe_push(
    body: schemas.PushUnsubscribeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    service.unsubscribe_push(db, user.id, endpoint=body.endpoint)
    return None


@router.get("/me/channel-links", response_model=list[schemas.ChannelLinkOut])
def list_links(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_links(db, user.id)


@router.post("/me/channel-links/{channel}/token", response_model=schemas.LinkTokenOut)
def create_link_token(
    channel: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.create_link_token(db, user.id, channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/me/channel-links/{channel}", status_code=204)
def delete_link(
    channel: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    service.unlink(db, user.id, channel)
    return None


@router.post("/notify/bot/link")
def bot_link(body: schemas.BotVerifyIn, request: Request, db: Session = Depends(get_db)):
    """Bot webhook: verifies shared secret, then links the token owner."""
    secret = os.environ.get("BOT_WEBHOOK_SECRET") or ""
    provided = request.headers.get("x-bot-secret") or ""
    if not secret or provided != secret:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        return service.verify_link_token(db, token=body.token, channel=body.channel,
                                         external_id=body.external_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/me/notify-preferences", response_model=list[schemas.PreferenceOut])
def get_prefs(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.preferences_matrix(db, user.id)


@router.patch("/me/notify-preferences", response_model=schemas.PreferenceOut)
def set_pref(
    body: schemas.PreferenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.set_p11_preference(db, user.id, category=body.category,
                                          channel=body.channel, enabled=body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/me/analytics", status_code=204)
def post_analytics(
    body: schemas.AnalyticsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        service.track(db, user_id=user.id, type=body.type, props=body.props)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return None
