"""The query surface: the raw replies of RFC 8522 sec. 3.2, through the guard and the HTTPS client.

``rib`` and ``detail`` build the guarded request, send it with ``transport.call`` and return what
the server said, untouched: a ``Success``, ``Fail`` or ``Error`` whose ``data["output"]`` is the
text the router printed. No typed BGP object is made, because that text is vendor-specific (the
RFC 8522 sec. 3.2 examples are Cisco-style) and carries no wire attributes for ``pathattr`` to
decode; typed results need a per-device parser (ROADMAP.md, ``parsers.per-device-fixtures``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .guard import assert_read_only
from .transport import call

if TYPE_CHECKING:
    from .protocol import Error, Fail, Success
    from .transport import Budget, Site

__all__ = [
    "detail",
    "rib",
]


async def rib(
    site: Site, prefix: str, *, budget: Budget | None = None, **query: str | int
) -> Success | Fail | Error:
    """The raw reply of ``show route {prefix}`` (RFC 8522 sec. 3.2.1), mandatory on every server.

    ``query`` are RFC 8522 sec. 2.2 query parameters (``protocol``, ``router``, ``vrf``, ...);
    the guard refuses any other name. ``prefix`` is an address or prefix, never a command.
    """
    return await call(site, assert_read_only("show route", prefix, **query), budget)


async def detail(
    site: Site, prefix: str, *, budget: Budget | None = None, **query: str | int
) -> Success | Fail | Error:
    """The raw reply of ``show bgp {prefix}`` (RFC 8522 sec. 3.2.2), optional on a server.

    A server that does not implement it answers with an ``Error`` or ``Fail`` reply, which is
    returned as it came.
    """
    return await call(site, assert_read_only("show bgp", prefix, **query), budget)
