"""API versioning foundation.

All platform APIs live under a single versioned prefix. Routers define
their resource prefix only (e.g. "/auth"); main.py mounts them under
API_V1_PREFIX. New API versions require an explicit compatibility
strategy (see docs/platform/API_CONTRACTS.md) — never a second
ad-hoc prefix.
"""

API_V1_PREFIX = "/api/v1"
