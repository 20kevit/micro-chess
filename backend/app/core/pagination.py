"""Shared pagination bounds (see docs/platform/API_CONTRACTS.md sections 47-50).

List endpoints accept ``page``/``page_size`` with a server-enforced
maximum so clients can never request unbounded records. The full
``{items, pagination}`` envelope is a later versioned change; for now
endpoints keep their response shape and only gain bounds.
"""

from typing import Annotated

from fastapi import Query

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

PageQuery = Annotated[int, Query(ge=1, description="1-based page number")]
PageSizeQuery = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page")]


def apply_pagination(query, *, page: int, page_size: int):
    return query.offset((page - 1) * page_size).limit(page_size)
