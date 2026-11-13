"""One query to many looking glasses, each site accounted for on its own.

RFC 8522 does not specify this. Its sec. 1.1 says a uniform command set matters when "multiple
Looking Glasses are part of a monitoring system", and every call in sec. 2 is "stateless and
independent" and goes to one server. So this module is a convention of this client: it sends the
same guarded request to each site concurrently and returns one ``SiteResult`` per site, in the
order the sites were given. A site that fails, times out or answers badly produces a ``SiteResult``
with its ``error`` set and never changes another site's result or raises for the batch.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .guard import ReadOnlyRequest
from .protocol import ResponseError
from .transport import TransportError, call

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .protocol import Error, Fail, Success
    from .transport import Budget, Site

__all__ = [
    "MAX_CONCURRENT",
    "SiteResult",
    "query_many",
]

MAX_CONCURRENT = 8
"""Most sites queried at once. A convention: RFC 8522 sec. 6.1 asks servers to guard against abuse,
and a client that opens a connection per site without bound is the abuse."""


@dataclass(frozen=True, slots=True)
class SiteResult:
    """What one site returned: the decoded reply or the reason there is none, and how long it took."""

    site: Site
    reply: Success | Fail | Error | None
    error: str | None
    seconds: float


async def query_many(
    sites: Sequence[Site],
    query: ReadOnlyRequest,
    budget: Budget | None = None,
    *,
    max_concurrent: int = MAX_CONCURRENT,
) -> list[SiteResult]:
    """Send ``query`` to every site and return one ``SiteResult`` each, in ``sites`` order.

    There is no RFC 8522 text for this (see the module docstring), so the rule is this library's:
    a ``TransportError`` or ``ResponseError`` from one site becomes that site's ``error`` and
    nothing else; a ``TypeError`` (a query that was not made by the guard) is a bug in the caller
    and is raised before any connection.
    """
    if not isinstance(query, ReadOnlyRequest):
        raise TypeError("query_many() takes a ReadOnlyRequest made by lgc.guard.assert_read_only")
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be at least 1")
    gate = asyncio.Semaphore(max_concurrent)

    async def one(site: Site) -> SiteResult:
        start = time.monotonic()
        async with gate:
            try:
                reply = await call(site, query, budget)
            except (TransportError, ResponseError) as error:
                return SiteResult(site, None, str(error), time.monotonic() - start)
        return SiteResult(site, reply, None, time.monotonic() - start)

    return list(await asyncio.gather(*(one(site) for site in sites)))
