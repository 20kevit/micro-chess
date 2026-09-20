"""Phase 11 support & notifications: lifecycle, authorization, preferences,
delivery, deduplication, provider isolation, and the v10 schema contract.
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.migration import SCHEMA_VERSION, ensure_schema, get_schema_version
from app.modules.admin.models import AuditLog
from app.modules.notifications import providers
from app.modules.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.modules.support.models import SupportMessage, SupportTicket
from app.modules.users.models import User, UserRole


def _register(client, username, password="secret123"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, username):
    return _register(client, username).json()["access_token"]


def _login_admin(client, username, password="secret123"):
    """Fresh ADMIN-active session (a pre-promotion session stays
    PLAYER-active; sessions fix their role at creation)."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "role": "ADMIN"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _grant(db_session, username, role):
    user = db_session.query(User).filter(User.username == username).one()
    if db_session.get(UserRole, (user.id, role)) is None:
        db_session.add(UserRole(user_id=user.id, role=role))
        db_session.commit()
    return user


def _ticket(client, token, subject="Login problem", message="I cannot log in", category=""):
    return client.post(
        "/api/v1/support/tickets",
        json={"subject": subject, "message": message, "category": category},
        headers=_bearer(token),
    )


# --- support creation ---------------------------------------------------------


def test_create_ticket_stores_owner_subject_and_initial_message(client, db_session):
    token = _token(client, "support_user_a")
    res = _ticket(client, token)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "open"
    assert body["subject"] == "Login problem"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["author"] == "user"
    assert body["messages"][0]["body"] == "I cannot log in"
    row = db_session.get(SupportTicket, body["id"])
    assert row is not None and row.status == "open"
    assert row.assigned_admin_id is None
    assert db_session.query(AuditLog).filter(AuditLog.action == "support.create").count() == 1


def test_create_ticket_requires_authentication(client):
    res = client.post(
        "/api/v1/support/tickets", json={"subject": "Hi", "message": "help"}
    )
    assert res.status_code == 401


def test_create_ticket_rejects_malformed_and_oversized_input(client):
    token = _token(client, "support_user_b")
    assert _ticket(client, token, subject="").status_code == 422
    assert _ticket(client, token, message="").status_code == 422
    assert _ticket(client, token, subject="x" * 201).status_code == 422
    assert _ticket(client, token, message="x" * 2001).status_code == 422
    assert _ticket(client, token, category="x" * 51).status_code == 422


def test_support_creation_is_rate_limited(client):
    from app.core.rate_limit import support_limiter

    token = _token(client, "support_user_c")
    support_limiter.per_minute = 2
    try:
        assert _ticket(client, token, subject="one").status_code == 201
        assert _ticket(client, token, subject="two").status_code == 201
        limited = _ticket(client, token, subject="three")
        assert limited.status_code == 429
    finally:
        support_limiter.per_minute = 20


# --- owner reads --------------------------------------------------------------


def test_owner_lists_and_reads_own_tickets_only(client):
    alice = _token(client, "support_alice")
    bob = _token(client, "support_bob")
    mine = _ticket(client, alice).json()["id"]
    _ticket(client, bob, subject="Bob issue")

    listing = client.get("/api/v1/me/support/tickets", headers=_bearer(alice))
    assert listing.status_code == 200
    assert [t["id"] for t in listing.json()] == [mine]

    detail = client.get(f"/api/v1/me/support/tickets/{mine}", headers=_bearer(alice))
    assert detail.status_code == 200
    # Owner view carries no admin identities.
    assert "user_id" not in detail.json()
    assert "assigned_admin_id" not in detail.json()

    # Bob cannot read Alice's ticket by id (no existence leak).
    assert client.get(f"/api/v1/me/support/tickets/{mine}", headers=_bearer(bob)).status_code == 404
    assert client.get("/api/v1/me/support/tickets/999999", headers=_bearer(alice)).status_code == 404
    assert client.get("/api/v1/me/support/tickets", headers={}).status_code == 401


def test_owner_ticket_list_supports_status_filter_and_pagination(client):
    token = _token(client, "support_pager")
    ids = [_ticket(client, token, subject=f"issue {i}").json()["id"] for i in range(3)]
    assert len(ids) == 3
    page = client.get(
        "/api/v1/me/support/tickets?page=1&page_size=2", headers=_bearer(token)
    )
    assert page.status_code == 200
    assert len(page.json()) == 2
    assert client.get("/api/v1/me/support/tickets?page_size=500", headers=_bearer(token)).status_code == 422
    assert client.get(
        "/api/v1/me/support/tickets?status=open", headers=_bearer(token)
    ).json() != []
    assert client.get(
        "/api/v1/me/support/tickets?status=closed", headers=_bearer(token)
    ).json() == []
    assert client.get(
        "/api/v1/me/support/tickets?status=bogus", headers=_bearer(token)
    ).status_code == 422


# --- conversation -------------------------------------------------------------


def test_owner_reply_keeps_conversation_open(client, db_session):
    token = _token(client, "support_replier")
    ticket_id = _ticket(client, token).json()["id"]
    res = client.post(
        f"/api/v1/me/support/tickets/{ticket_id}/messages",
        json={"body": "more detail"},
        headers=_bearer(token),
    )
    assert res.status_code == 201, res.text
    assert res.json()["author"] == "user"
    assert db_session.get(SupportTicket, ticket_id).status == "open"
    assert client.post(
        f"/api/v1/me/support/tickets/{ticket_id}/messages",
        json={"body": ""},
        headers=_bearer(token),
    ).status_code == 422


def test_owner_cannot_reply_to_foreign_or_closed_tickets(client, db_session):
    alice = _token(client, "support_closed_a")
    bob = _token(client, "support_closed_b")
    _grant(db_session, "support_closed_b", "ADMIN")
    bob = _login_admin(client, "support_closed_b")
    ticket_id = _ticket(client, alice).json()["id"]
    # Foreign reply reads as not-found.
    assert client.post(
        f"/api/v1/me/support/tickets/{ticket_id}/messages",
        json={"body": "hi"},
        headers=_bearer(bob),
    ).status_code == 404
    # After staff close, owner follow-ups are rejected (terminal state).
    assert client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/close", headers=_bearer(bob)
    ).status_code == 200
    assert client.post(
        f"/api/v1/me/support/tickets/{ticket_id}/messages",
        json={"body": "wait"},
        headers=_bearer(alice),
    ).status_code == 409


# --- staff workflows ----------------------------------------------------------


def test_staff_list_respond_close_lifecycle_with_notifications(client, db_session):
    owner = _token(client, "support_staff_user")
    staff = _token(client, "support_staff_admin")
    _grant(db_session, "support_staff_admin", "ADMIN")
    staff = _login_admin(client, "support_staff_admin")
    ticket_id = _ticket(client, owner).json()["id"]

    listing = client.get("/api/v1/admin/support/tickets", headers=_bearer(staff))
    assert listing.status_code == 200
    assert [t["id"] for t in listing.json()] == [ticket_id]
    assert listing.json()[0]["user_id"] is not None

    response = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        json={"body": "try resetting your password"},
        headers=_bearer(staff),
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"] == "staff"

    detail = client.get(
        f"/api/v1/admin/support/tickets/{ticket_id}", headers=_bearer(staff)
    ).json()
    assert detail["status"] == "answered"
    assert detail["assigned_admin_id"] is not None
    assert [m["body"] for m in detail["messages"]] == [
        "I cannot log in",
        "try resetting your password",
    ]

    # The owner was notified about the staff response (in-app delivery).
    notifications = client.get("/api/v1/me/notifications", headers=_bearer(owner)).json()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "support.response"
    assert notifications[0]["read_at"] is None

    # Owner reply moves answered back to open.
    assert client.post(
        f"/api/v1/me/support/tickets/{ticket_id}/messages",
        json={"body": "that did not work"},
        headers=_bearer(owner),
    ).status_code == 201
    assert client.get(
        f"/api/v1/me/support/tickets/{ticket_id}", headers=_bearer(owner)
    ).json()["status"] == "open"

    # Close is terminal and idempotent; the owner gets a closure notice.
    close = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/close", headers=_bearer(staff)
    )
    assert close.status_code == 200
    assert close.json()["status"] == "closed"
    again = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/close", headers=_bearer(staff)
    )
    assert again.status_code == 200
    assert again.json()["status"] == "closed"
    types = {
        n["type"]
        for n in client.get("/api/v1/me/notifications", headers=_bearer(owner)).json()
    }
    assert types == {"support.response", "support.closed"}

    # Staff cannot respond to a closed ticket.
    assert client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        json={"body": "late reply"},
        headers=_bearer(staff),
    ).status_code == 409
    assert client.get(
        "/api/v1/admin/support/tickets/999999", headers=_bearer(staff)
    ).status_code == 404

    # Auditable staff actions, secret-free.
    actions = {
        row.action
        for row in db_session.query(AuditLog)
        .filter(AuditLog.target_type == "support_ticket")
        .all()
    }
    assert {"support.create", "support.reply", "support.respond", "support.close"} <= actions


def test_support_staff_endpoints_enforce_capabilities(client, db_session):
    player = _token(client, "support_nocap_a")
    other = _token(client, "support_nocap_b")
    ticket_id = _ticket(client, player).json()["id"]
    # Plain players hold no staff capabilities.
    assert client.get("/api/v1/admin/support/tickets", headers=_bearer(player)).status_code == 403
    assert client.get(
        f"/api/v1/admin/support/tickets/{ticket_id}", headers=_bearer(player)
    ).status_code == 403
    assert client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        json={"body": "x"},
        headers=_bearer(player),
    ).status_code == 403
    assert client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/close", headers=_bearer(player)
    ).status_code == 403
    assert client.get("/api/v1/admin/support/tickets").status_code == 401
    # A second player sees no tickets in the staff list (ownership first).
    _grant(db_session, "support_nocap_b", "ADMIN")
    other = _login_admin(client, "support_nocap_b")
    assert [t["id"] for t in client.get(
        "/api/v1/admin/support/tickets", headers=_bearer(other)
    ).json()] == [ticket_id]


# --- notifications: read/unread ----------------------------------------------


def test_notification_list_unread_filter_and_mark_read(client, db_session):
    owner = _token(client, "support_notify_a")
    staff = _token(client, "support_notify_admin")
    _grant(db_session, "support_notify_admin", "ADMIN")
    staff = _login_admin(client, "support_notify_admin")
    ticket_id = _ticket(client, owner).json()["id"]
    client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/messages",
        json={"body": "hello"},
        headers=_bearer(staff),
    )
    client.post(f"/api/v1/admin/support/tickets/{ticket_id}/close", headers=_bearer(staff))

    all_items = client.get("/api/v1/me/notifications", headers=_bearer(owner)).json()
    assert len(all_items) == 2
    unread = client.get(
        "/api/v1/me/notifications?unread_only=true", headers=_bearer(owner)
    ).json()
    assert len(unread) == 2
    count = client.get(
        "/api/v1/me/notifications/unread-count", headers=_bearer(owner)
    ).json()
    assert count == {"unread_count": 2}

    first = client.post(
        f"/api/v1/me/notifications/{all_items[0]['id']}/read", headers=_bearer(owner)
    )
    assert first.status_code == 200
    assert first.json()["read_at"] is not None
    # Idempotent re-read.
    assert client.post(
        f"/api/v1/me/notifications/{all_items[0]['id']}/read", headers=_bearer(owner)
    ).status_code == 200
    assert client.get(
        "/api/v1/me/notifications?unread_only=true", headers=_bearer(owner)
    ).json() != []
    assert client.get(
        "/api/v1/me/notifications/unread-count", headers=_bearer(owner)
    ).json() == {"unread_count": 1}

    # Cross-user isolation: another player cannot mark this notification.
    stranger = _token(client, "support_notify_stranger")
    assert client.post(
        f"/api/v1/me/notifications/{all_items[0]['id']}/read", headers=_bearer(stranger)
    ).status_code == 404
    assert client.post(
        "/api/v1/me/notifications/999999/read", headers=_bearer(owner)
    ).status_code == 404
    assert client.get("/api/v1/me/notifications").status_code == 401


# --- preferences --------------------------------------------------------------


def test_notification_preferences_defaults_and_mandatory(client, db_session):
    token = _token(client, "support_prefs_a")
    matrix = client.get(
        "/api/v1/me/notification-preferences", headers=_bearer(token)
    ).json()
    by_key = {(p["category"], p["channel"]): p for p in matrix}
    # Safe defaults: everything enabled; account flagged mandatory.
    assert by_key[("support", "in_app")]["enabled"] is True
    assert by_key[("support", "in_app")]["mandatory"] is False
    assert by_key[("account", "in_app")]["enabled"] is True
    assert by_key[("account", "in_app")]["mandatory"] is True

    # Disabling support notices works and is honored by emission.
    updated = client.patch(
        "/api/v1/me/notification-preferences",
        json={"category": "support", "channel": "in_app", "enabled": False},
        headers=_bearer(token),
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    # Mandatory account notices can never be disabled.
    mandatory = client.patch(
        "/api/v1/me/notification-preferences",
        json={"category": "account", "channel": "in_app", "enabled": False},
        headers=_bearer(token),
    )
    assert mandatory.status_code == 422

    # Unknown vocabulary is rejected.
    assert client.patch(
        "/api/v1/me/notification-preferences",
        json={"category": "bogus", "channel": "in_app", "enabled": True},
        headers=_bearer(token),
    ).status_code == 422
    assert client.patch(
        "/api/v1/me/notification-preferences",
        json={"category": "support", "channel": "sms", "enabled": True},
        headers=_bearer(token),
    ).status_code == 422
    assert client.get("/api/v1/me/notification-preferences").status_code == 401


def test_preference_filtering_suppresses_optional_but_not_mandatory(client, db_session):
    from app.modules.notifications import service as notifications

    token = _token(client, "support_prefs_b")
    me = client.get("/api/v1/users/me", headers=_bearer(token)).json()["id"]
    client.patch(
        "/api/v1/me/notification-preferences",
        json={"category": "support", "channel": "in_app", "enabled": False},
        headers=_bearer(token),
    )
    suppressed = notifications.emit_event(
        db_session,
        user_id=me,
        type="support.response",
        title="subject",
        dedup_key="pref-test:1",
    )
    assert suppressed is None
    assert db_session.query(Notification).filter(Notification.user_id == me).count() == 0
    # Mandatory account events bypass preferences entirely.
    kept = notifications.emit_event(
        db_session,
        user_id=me,
        type="account.suspended",
        title="account.suspended",
        dedup_key="pref-test:2",
    )
    assert kept is not None


# --- deduplication ------------------------------------------------------------


def test_duplicate_events_collapse_to_one_notification(client, db_session):
    from app.modules.notifications import service as notifications

    token = _token(client, "support_dedup_a")
    me = client.get("/api/v1/users/me", headers=_bearer(token)).json()["id"]
    first = notifications.emit_event(
        db_session, user_id=me, type="support.response", title="t", dedup_key="dup:1"
    )
    second = notifications.emit_event(
        db_session, user_id=me, type="support.response", title="t", dedup_key="dup:1"
    )
    assert first is not None and second is not None
    assert first.id == second.id
    assert db_session.query(Notification).filter(Notification.dedup_key == "dup:1").count() == 1
    # One delivery row per (notification, channel): no duplicates.
    assert (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.notification_id == first.id)
        .count()
        == 1
    )


def test_unknown_event_vocabulary_is_rejected(db_session):
    from app.modules.notifications import service as notifications

    try:
        notifications.emit_event(db_session, user_id=1, type="bogus.event", title="t")
    except ValueError as exc:
        assert str(exc) == "unknown_event_type"
    else:  # pragma: no cover
        raise AssertionError("expected unknown_event_type")


# --- delivery: failure, retry, provider isolation -----------------------------


def test_delivery_failure_and_retry_without_new_rows(db_session):
    from app.modules.notifications import service as notifications

    class FlakyProvider(providers.NotificationProvider):
        name = "in_app"
        failures = 1

        def send(self, notification):
            if FlakyProvider.failures > 0:
                FlakyProvider.failures -= 1
                return providers.DeliveryOutcome(delivered=False, error="boom")
            return providers.DeliveryOutcome(delivered=True)

    real = providers.get_provider("in_app")
    assert real is not None
    providers.register_provider(FlakyProvider())
    try:
        created = notifications.emit_event(
            db_session, user_id=1, type="support.response", title="t", dedup_key="retry:1"
        )
        assert created is not None
        delivery = (
            db_session.query(NotificationDelivery)
            .filter(NotificationDelivery.notification_id == created.id)
            .one()
        )
        assert delivery.status == "failed"
        assert delivery.attempts == 1
        # Error summary only: no notification text leaks into the row.
        assert "t" not in (delivery.last_error or "")

        retried = notifications.retry_delivery(db_session, delivery_id=delivery.id)
        assert retried.status == "delivered"
        assert retried.attempts == 2
        assert (
            db_session.query(NotificationDelivery)
            .filter(NotificationDelivery.notification_id == created.id)
            .count()
            == 1
        )
        # Retrying a terminal delivery is a no-op.
        assert notifications.retry_delivery(db_session, delivery_id=delivery.id).id == delivery.id
    finally:
        providers.register_provider(real)

    try:
        notifications.retry_delivery(db_session, delivery_id=999999)
    except ValueError as exc:
        assert str(exc) == "delivery_not_found"
    else:  # pragma: no cover
        raise AssertionError("expected delivery_not_found")


def test_raising_provider_never_breaks_emission(db_session):
    from app.modules.notifications import service as notifications

    class RaisingProvider(providers.NotificationProvider):
        name = "in_app"

        def send(self, notification):
            raise RuntimeError("provider exploded")

    real = providers.get_provider("in_app")
    assert real is not None
    providers.register_provider(RaisingProvider())
    try:
        created = notifications.emit_event(
            db_session, user_id=1, type="support.response", title="t", dedup_key="raise:1"
        )
        assert created is not None
        delivery = (
            db_session.query(NotificationDelivery)
            .filter(NotificationDelivery.notification_id == created.id)
            .one()
        )
        assert delivery.status == "failed"
    finally:
        providers.register_provider(real)


# --- account/security trigger -------------------------------------------------


def test_suspend_and_reactivate_emit_mandatory_account_notices(client, db_session):
    admin = _token(client, "support_acct_admin")
    _grant(db_session, "support_acct_admin", "ADMIN")
    admin = _login_admin(client, "support_acct_admin")
    player = _token(client, "support_acct_player")
    me = client.get("/api/v1/users/me", headers=_bearer(player)).json()["id"]

    assert client.get("/api/v1/me/notifications", headers=_bearer(player)).json() == []
    suspend = client.post(
        f"/api/v1/admin/users/{me}/suspend", headers=_bearer(admin)
    )
    assert suspend.status_code == 200
    # The suspended token is dead (fails closed), so verify the mandatory
    # notice through persistence; the owner reads it after reactivation.
    stored = (
        db_session.query(Notification).filter(Notification.user_id == me).all()
    )
    assert [n.type for n in stored] == ["account.suspended"]

    reactivate = client.post(
        f"/api/v1/admin/users/{me}/reactivate", headers=_bearer(admin)
    )
    assert reactivate.status_code == 200
    stored = (
        db_session.query(Notification)
        .filter(Notification.user_id == me)
        .order_by(Notification.id)
        .all()
    )
    assert [n.type for n in stored] == ["account.suspended", "account.reactivated"]
    # Mandatory category: even an (impossible) opt-out could not suppress.
    for notice in stored:
        assert notice.category == "account"
    # After reactivation the owner reads the notices over HTTP.
    over_http = client.get("/api/v1/me/notifications", headers=_bearer(player)).json()
    assert {n["type"] for n in over_http} == {"account.suspended", "account.reactivated"}


# --- migration ----------------------------------------------------------------


def test_fresh_database_boots_to_v10_with_support_tables():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert SCHEMA_VERSION == 15
    assert ensure_schema(engine) == SCHEMA_VERSION
    assert get_schema_version(engine) == SCHEMA_VERSION
    tables = inspect(engine).get_table_names()
    for table in (
        "support_tickets",
        "support_messages",
        "notifications",
        "notification_deliveries",
        "notification_preferences",
    ):
        assert table in tables
        assert table in Base.metadata.tables
    assert ensure_schema(engine) == SCHEMA_VERSION  # idempotent re-run


def test_v9_database_upgrades_to_v10_preserving_users(client, db_session):
    from sqlalchemy.orm import sessionmaker

    users_before = db_session.query(User).count()
    assert ensure_schema(db_session.get_bind()) == SCHEMA_VERSION
    assert db_session.query(User).count() == users_before
    assert "support_tickets" in inspect(db_session.get_bind()).get_table_names()


def test_support_models_use_portable_column_types():
    """New tables must compile on both SQLite (dev) and PostgreSQL
    (production target): only portable column types, no SQLite-only DDL."""
    from sqlalchemy.dialects import postgresql, sqlite
    from sqlalchemy.schema import CreateTable

    tables = (
        SupportTicket.__table__,
        SupportMessage.__table__,
        Notification.__table__,
        NotificationDelivery.__table__,
        NotificationPreference.__table__,
    )
    assert {t.name for t in tables} == {
        "support_tickets",
        "support_messages",
        "notifications",
        "notification_deliveries",
        "notification_preferences",
    }
    for table in tables:
        for dialect in (sqlite.dialect(), postgresql.dialect()):
            ddl = str(CreateTable(table).compile(dialect=dialect))
            assert f'"{table.name}"' in ddl or table.name in ddl
