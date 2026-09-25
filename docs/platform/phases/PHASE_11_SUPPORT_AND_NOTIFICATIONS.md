# Phase 11 — Support & Notifications

## 1. Goal

Provide reliable user support and a notification foundation without coupling the platform to a specific external messaging provider.

---

## 2. Scope

Implement:

* support requests
* support conversations/responses
* notification preferences
* in-app notifications
* notification events
* delivery status
* read/unread state
* provider abstraction for future email/push/messaging integrations

External delivery providers are optional and should be added only when required.

---

## 3. Support

Players can create support requests using:

```text
support.create
```

Users can access their own requests through:

```text
support.read_own
```

Authorized staff/admins may:

```text
support.read
support.respond
support.close
support.manage
```

A closed ticket can be explicitly reopened by authorized staff. Reopening
returns it to `open`, preserves all messages, and records an audit event;
it does not create a second ticket or delete history.

A support request should retain:

* requester
* subject/category
* messages
* status
* timestamps
* assigned administrator where applicable
* audit information

---

## 4. Notification Model

Notifications should distinguish:

```text
event
→ notification
→ delivery
```

The platform event describes what happened.

A notification determines what the user should see.

A delivery represents an attempt to send it through a specific channel.

This separation allows future channels without changing domain events.

---

## 5. Channels

Initial priority:

```text
IN_APP
```

Future channels may include:

```text
EMAIL
PUSH
TELEGRAM
OTHER_MESSAGING
```

The notification domain must not depend directly on a provider SDK.

---

## 6. Preferences

Users should eventually control notification preferences by:

* category
* channel
* frequency where applicable

Mandatory security/account notifications may not be disableable.

Preferences must be respected before non-critical delivery.

---

## 7. Reliability

Notification creation should not fail the underlying business operation merely because an external delivery provider is unavailable.

External delivery should support:

* retry
* failure state
* idempotency
* provider-independent status
* logging without sensitive payload leakage

---

## 8. Privacy

Notifications must not expose unnecessary sensitive information.

Child/student notifications must respect relationship and privacy rules.

External providers should receive only the minimum required data.

---

## 9. Testing

Test:

* support creation
* authorization
* support lifecycle
* notification creation
* read/unread behavior
* preference filtering
* duplicate prevention
* delivery failure/retry
* provider isolation
* privacy

---

## 10. Definition of Done

Phase 11 is complete when:

* users can create and track support requests
* authorized staff can respond and close requests
* in-app notifications work reliably
* notification preferences are enforced
* delivery is separated from business events
* provider integrations remain replaceable
* failures do not corrupt core business operations
* meaningful support/notification tests pass
