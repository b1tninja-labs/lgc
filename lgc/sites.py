"""What a looking glass says it offers: the router list, router details and the command list.

RFC 8522 sec. 3.3 defines three organizational functions every server must provide: ``routers``
(sec. 3.3.1), ``routers/{number}`` (sec. 3.3.2) and ``cmd`` (sec. 3.3.3). These parsers read the
already decoded ``Success`` reply of each into a typed object, and ``discover`` fetches the first
and last through the guard and the HTTPS client. They need no vendor text: every member is one
the RFC prints.

What a server advertises is information, never permission. The guard still refuses any function
outside its own allow list, so ``supports`` only says whether the server listed a function that
the guard also knows. A reply with a member of the wrong type raises ``protocol.ResponseError``;
nothing is repaired.

Two things the RFC does not settle are kept visible rather than guessed (ROADMAP.md,
``finding.rfc8522-router-list-shape``): the sec. 3.3.1 prose says the list carries "the router ID
and its name" while its example is an array of host names with no ids, so only that array of
strings is accepted; and the number a ``routers/{number}`` request takes is not tied to a position
in that array, so the parsers offer no index of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .guard import FUNCTIONS, assert_read_only
from .protocol import ResponseError, Success
from .transport import call

if TYPE_CHECKING:
    from .protocol import Error, Fail
    from .transport import Budget, Site

__all__ = [
    "Capabilities",
    "Command",
    "RouterDetails",
    "discover",
    "parse_commands",
    "parse_router_details",
    "parse_router_list",
    "router_details",
]

_DEFAULT_FORMAT = "text/plain"
"""Sec. 3.3.2 para 4: a missing output format defaults to ``text/plain``."""


@dataclass(frozen=True, slots=True)
class RouterDetails:
    """One router (RFC 8522 sec. 3.3.2): ``id`` and ``name`` are required, the rest is optional.

    ``formats`` are the Internet media types the router offers, split at the commas of the
    ``format`` member; absent, it is ``("text/plain",)``. ``extra`` keeps every other member as
    sent (city, administrative contact, vendor, model and any the server adds).
    """

    id: int
    name: str
    formats: tuple[str, ...] = (_DEFAULT_FORMAT,)
    country: str | None = None
    autonomous_system: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Command:
    """One entry of the ``commands`` array (sec. 3.3.3): four informative strings.

    ``command`` and ``href`` are required. ``arguments`` (a template such as ``{addr}``) and
    ``description`` are ``None`` when the server left them out.
    """

    command: str
    href: str
    arguments: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What ``discover`` learned from one server: its routers (by name) and its commands."""

    routers: tuple[str, ...]
    commands: tuple[Command, ...]

    def supports(self, function: str) -> bool:
        """True when the server listed ``function`` and this client's allow list knows it.

        The comparison is on the ``command`` string, case-insensitively. A server listing a
        command the guard does not know (an extension, sec. 3.4) is not "supported" here: the
        client could not send it. The mandatory functions of sec. 3 are not assumed present.
        """
        name = function.lower()
        if name not in FUNCTIONS:
            return False
        return any(c.command.lower() == name for c in self.commands)

    def extensions(self) -> tuple[Command, ...]:
        """Listed commands outside the guard's allow list (sec. 3.4), reported and never sent."""
        return tuple(c for c in self.commands if c.command.lower() not in FUNCTIONS)


def _data(reply: Success | Fail | Error) -> dict[str, Any]:
    if not isinstance(reply, Success):
        raise ResponseError(f"a {reply.status} reply carries no listing")
    return reply.data


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResponseError(f"{what} must be a non-empty string")
    return value


def parse_router_list(reply: Success | Fail | Error) -> tuple[str, ...]:
    """The host names of ``data["routers"]`` (RFC 8522 sec. 3.3.1), in the order sent.

    Only the array of strings the sec. 3.3.1 example prints is accepted; see the module note on
    the "router ID" wording. Raises ``ResponseError`` for a non-success reply, a missing or
    non-array ``routers``, or a member that is not a non-empty string.
    """
    data = _data(reply)
    if "routers" not in data:
        raise ResponseError('router list: data has no "routers" member (RFC 8522 sec. 3.3.1)')
    routers = data["routers"]
    if not isinstance(routers, list):
        raise ResponseError('router list: "routers" must be an array')
    return tuple(_text(item, "a router name") for item in routers)


def parse_router_details(reply: Success | Fail | Error) -> RouterDetails:
    """The typed router of a ``routers/{number}`` reply (RFC 8522 sec. 3.3.2).

    The response "must contain the router's hostname and router index", so ``id`` (an integer)
    and ``name`` are required. ``format`` is a comma separated list of media types; ``country``
    and ``autonomous_system`` are read when present; every other member lands in ``extra``.
    """
    data = _data(reply)
    ident = data.get("id")
    if isinstance(ident, bool) or not isinstance(ident, int):
        raise ResponseError('router details: "id" must be an integer (RFC 8522 sec. 3.3.2 para 1)')
    name = _text(data.get("name"), 'router details: "name"')
    formats: tuple[str, ...] = (_DEFAULT_FORMAT,)
    if "format" in data:
        raw = _text(data["format"], 'router details: "format"')
        parts = tuple(part.strip() for part in raw.split(","))
        if not all(parts):
            raise ResponseError('router details: "format" has an empty media type')
        formats = parts
    country = data.get("country")
    if country is not None and not isinstance(country, str):
        raise ResponseError('router details: "country" must be a string')
    asn = data.get("autonomous_system")
    if asn is not None and (isinstance(asn, bool) or not isinstance(asn, int) or asn < 0):
        raise ResponseError('router details: "autonomous_system" must be a non-negative integer')
    known = {"id", "name", "format", "country", "autonomous_system"}
    extra = {k: v for k, v in data.items() if k not in known}
    return RouterDetails(ident, name, formats, country, asn, extra)


def parse_commands(reply: Success | Fail | Error) -> tuple[Command, ...]:
    """The entries of ``data["commands"]`` (RFC 8522 sec. 3.3.3), in the order sent.

    Each entry is an object with the informative strings ``command``, ``href``, ``arguments`` and
    ``description``. ``command`` and ``href`` are required here, since an entry without either
    says nothing a client can use; the other two may be absent. Other members are ignored.
    """
    data = _data(reply)
    if "commands" not in data:
        raise ResponseError('commands: data has no "commands" member (RFC 8522 sec. 3.3.3)')
    entries = data["commands"]
    if not isinstance(entries, list):
        raise ResponseError('commands: "commands" must be an array')
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ResponseError("commands: every entry must be an object")
        optional = {}
        for key in ("arguments", "description"):
            value = entry.get(key)
            if value is not None and not isinstance(value, str):
                raise ResponseError(f"commands: {key!r} must be a string")
            optional[key] = value
        out.append(
            Command(
                _text(entry.get("command"), 'commands: "command"'),
                _text(entry.get("href"), 'commands: "href"'),
                optional["arguments"],
                optional["description"],
            )
        )
    return tuple(out)


async def router_details(site: Site, index: int, *, budget: Budget | None = None) -> RouterDetails:
    """Fetch and parse ``routers/{index}`` (RFC 8522 sec. 3.3.2).

    The reply is decoded with ``function="router details"`` (``transport.call`` passes it)
    because the sec. 3.3.2 example has no timing members. A non-success reply raises
    ``ResponseError``.
    """
    reply = await call(site, assert_read_only("router details", index), budget)
    return parse_router_details(reply)


async def discover(site: Site, *, budget: Budget | None = None) -> Capabilities:
    """Ask one server for its router list and command list (RFC 8522 sec. 3.3.1 and 3.3.3).

    Both functions are mandatory on every server (sec. 3.3 para 1), so a failure of either is
    an error, not an empty answer. A transport failure raises ``transport.TransportError``.
    """
    routers = parse_router_list(await call(site, assert_read_only("router list"), budget))
    commands = parse_commands(await call(site, assert_read_only("commands"), budget))
    return Capabilities(routers, commands)
