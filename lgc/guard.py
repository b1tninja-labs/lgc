"""Read-only enforcement: the closed list of RFC 8522 functions and the only way to build a request.

RFC 8522 sec. 3 para 2: "It is not possible for any function to modify the server's state.
Therefore, all HTTP methods are GET operations." Sec. 2 para 3: the client must not be able to
execute random commands on the router. This module is that property made structural. A
``ReadOnlyRequest`` can be made only by ``assert_read_only``, which accepts a function name from
``FUNCTIONS`` (nothing else), one argument checked for the shape that function takes, and query
parameters from ``QUERY_PARAMETERS`` (nothing else) with values checked against a closed syntax.
There is no raw-command path and there will not be one (README non-goal). The transport takes a
``ReadOnlyRequest`` and nothing it could build itself.

Where a bound below is not in RFC 8522 it is labelled "convention": a limit this library chose so
that a hostile value cannot reach the wire, not a limit the RFC states.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote

__all__ = [
    "FUNCTIONS",
    "PREFIX",
    "QUERY_PARAMETERS",
    "FunctionSpec",
    "ReadOnlyRequest",
    "RefusedQuery",
    "assert_read_only",
]

PREFIX = "/.well-known/looking-glass/v1/"
"""The path prefix: ``.well-known/looking-glass`` (RFC 8522 sec. 2 para 2, sec. 5.1) and the ``v1``
every sec. 3 syntax line shows."""

ArgKind = Literal["none", "prefix", "address", "host", "index"]


class RefusedQuery(ValueError):  # noqa: N818 - "refused" is the guard's own verb
    """The request is outside the allow list. Nothing was built and nothing can be sent."""


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    """One function RFC 8522 defines: where it lives, what argument it takes, who must offer it."""

    name: str
    segments: tuple[str, ...]
    arg: ArgKind
    mandatory: bool
    section: str


def _spec(name: str, segments: tuple[str, ...], arg: ArgKind, mandatory: bool, section: str):
    return name, FunctionSpec(name, segments, arg, mandatory, section)


FUNCTIONS: dict[str, FunctionSpec] = dict(
    [
        _spec("ping", ("ping",), "host", True, "3.1.1"),
        _spec("traceroute", ("traceroute",), "host", False, "3.1.2"),
        _spec("show route", ("show", "route"), "prefix", True, "3.2.1"),
        _spec("show bgp", ("show", "bgp"), "prefix", False, "3.2.2"),
        _spec("show bgp summary", ("show", "bgp", "summary"), "none", False, "3.2.3"),
        _spec("show bgp neighbors", ("show", "bgp", "neighbors"), "address", False, "3.2.4"),
        _spec("router list", ("routers",), "none", True, "3.3.1"),
        _spec("router details", ("routers",), "index", True, "3.3.2"),
        _spec("commands", ("cmd",), "none", True, "3.3.3"),
    ]
)
"""Every function, keyed by its RFC 8522 name. ``router list`` is the path ``routers`` and
``commands`` is the path ``cmd``: sec. 3.3.1 and 3.3.3 print those syntax lines (the sec. 3.3.3
example's ``href`` values end in ``show/route`` and ``traceroute`` without an argument, which is
not the syntax line either). The sec. 3.4 extension commands (for example ``show/ospf/database``)
are server-defined and are not here: a command nobody listed cannot be proved read-only."""

QUERY_PARAMETERS = frozenset(
    {"protocol", "router", "routerindex", "random", "vrf", "runtime", "format"}
)
"""The seven query parameters of RFC 8522 sec. 2.2."""

_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,254}")
_TOKEN64 = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_RANDOM = re.compile(r"[A-Za-z0-9]{1,64}")
_MEDIA_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}")
_DIGITS = re.compile(r"[0-9]{1,10}")

MAX_ROUTERINDEX = 65535
"""Convention: RFC 8522 sec. 2.2 says only "Number"."""
MAX_RUNTIME = 3600
"""Convention. Sec. 2.2: a ``runtime`` of 0 disables the server's limit, and this guard never asks
for that, because the limit is the server's protection against a command that does not end."""
MAX_FORMATS = 8
"""Convention: how many media types one ``format`` list may name."""

_TOKEN = object()


@dataclass(frozen=True, slots=True)
class ReadOnlyRequest:
    """A request that has passed the guard. Make one with ``assert_read_only``; nothing else does.

    ``path`` begins with ``PREFIX``. ``query`` is a tuple of ``(name, value)`` pairs, names in
    lower case and sorted, values as they will be sent after percent-encoding. ``method`` is
    always ``"GET"``. Building one directly raises ``TypeError``: the constructor wants a token
    only this module holds. (Python cannot make that unforgeable; it makes it deliberate.)
    """

    function: str
    path: str
    query: tuple[tuple[str, str], ...]
    method: Literal["GET"] = "GET"
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _TOKEN:
            raise TypeError("a ReadOnlyRequest is made by lgc.guard.assert_read_only, nothing else")

    @property
    def target(self) -> str:
        """The request target: the path, then ``?`` and the query if there is one."""
        if not self.query:
            return self.path
        return self.path + "?" + "&".join(f"{name}={value}" for name, value in self.query)


def _address(text: str, what: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        raise RefusedQuery(f"{what}: {text!r} is not an IPv4 or IPv6 address") from None


def _check_arg(kind: ArgKind, value: object, function: str) -> tuple[str, ...]:
    """Return the path segments the argument adds. A refusal names the function and the rule."""
    if kind == "none":
        if value is not None:
            raise RefusedQuery(f"{function} takes no argument")
        return ()
    if value is None:
        raise RefusedQuery(f"{function} needs an argument")
    if kind == "index":
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise RefusedQuery(f"{function}: the router number must be a non-negative integer")
        text = str(value)
        if _DIGITS.fullmatch(text) is None or int(text) > MAX_ROUTERINDEX:
            raise RefusedQuery(
                f"{function}: the router number must be a non-negative integer, at most {MAX_ROUTERINDEX}"
            )
        return (str(int(text)),)
    if not isinstance(value, str) or not value:
        raise RefusedQuery(f"{function}: the argument must be a non-empty string")
    if value != value.strip() or not value.isascii() or any(c in value for c in "%?#\\ \t\r\n\x00"):
        raise RefusedQuery(
            f"{function}: the argument holds a character no address or host name has"
        )
    if kind == "address":
        return (str(_address(value, function)),)
    if kind == "prefix":
        if "/" not in value:
            return (str(_address(value, function)),)
        host, _, length = value.partition("/")
        address = _address(host, function)
        if _DIGITS.fullmatch(length) is None:
            raise RefusedQuery(f"{function}: {value!r} has no prefix length")
        try:
            network = ipaddress.ip_network(f"{address}/{length}", strict=True)
        except ValueError:
            raise RefusedQuery(
                f"{function}: {value!r} is not a prefix (host bits set or length out of range)"
            ) from None
        return (str(network.network_address), str(network.prefixlen))
    # kind == "host": a name or an address (RFC 8522 sec. 3.1.1 para 1)
    if ":" in value or value.replace(".", "").isdigit():
        return (str(_address(value, function)),)
    if len(value) > 253:
        raise RefusedQuery(f"{function}: host name longer than 253 characters")
    labels = value.split(".")
    if not all(_LABEL.fullmatch(label) for label in labels):
        raise RefusedQuery(f"{function}: {value!r} is not a host name")
    return (value.lower(),)


def _query_value(name: str, value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise RefusedQuery(f"{name}: the value must be a string or an integer")
    text = str(value)
    if name == "protocol":
        parts = text.split(",")
        if not 1 <= len(parts) <= 2 or not all(_DIGITS.fullmatch(p) for p in parts):
            raise RefusedQuery("protocol: AFI or AFI,SAFI as decimal numbers (RFC 8522 sec. 2.2)")
        afi, safi = int(parts[0]), (int(parts[1]) if len(parts) == 2 else None)
        if afi > 65535 or (safi is not None and safi > 255):
            raise RefusedQuery("protocol: AFI is two octets and SAFI one octet (RFC 4760 sec. 3)")
        return ",".join(str(int(p)) for p in parts)
    if name == "routerindex":
        if _DIGITS.fullmatch(text) is None or int(text) > MAX_ROUTERINDEX:
            raise RefusedQuery(f"routerindex: a number from 0 to {MAX_ROUTERINDEX}")
        return str(int(text))
    if name == "runtime":
        if _DIGITS.fullmatch(text) is None or not 1 <= int(text) <= MAX_RUNTIME:
            raise RefusedQuery(
                f"runtime: seconds from 1 to {MAX_RUNTIME}; 0 (no limit) is never sent"
            )
        return str(int(text))
    if name == "router":
        if _NAME.fullmatch(text) is None:
            raise RefusedQuery("router: a name of letters, digits and . _ : - (convention)")
        return quote(text, safe="")
    if name == "vrf":
        if _TOKEN64.fullmatch(text) is None:
            raise RefusedQuery("vrf: a name of letters, digits and . _ - (convention)")
        return quote(text, safe="")
    if name == "random":
        if _RANDOM.fullmatch(text) is None:
            raise RefusedQuery("random: letters and digits only (convention)")
        return text
    # format: media types, comma separated (sec. 2.2)
    formats = text.split(",")
    if len(formats) > MAX_FORMATS:
        raise RefusedQuery(f"format: at most {MAX_FORMATS} media types (convention)")
    for media in formats:
        kind, slash, subtype = media.partition("/")
        if not slash or not _MEDIA_PART.fullmatch(kind) or not _MEDIA_PART.fullmatch(subtype):
            raise RefusedQuery(f"format: {media!r} is not a type/subtype media type")
    return quote(text.lower(), safe=",/")


def assert_read_only(
    function: str, arg: str | int | None = None, **query: str | int
) -> ReadOnlyRequest:
    """Return the GET request for an allow-listed function, or raise ``RefusedQuery`` (RFC 8522 sec. 2, 3).

    ``function`` is a key of ``FUNCTIONS``, compared without regard to case because RFC 8522
    sec. 2 para 5 makes names and values case insensitive; the request carries the canonical lower
    case. ``arg`` is the one path argument that function takes: an IPv4 or IPv6 address or
    prefix, a host name, or a router number. Query parameter names must be in ``QUERY_PARAMETERS``.
    Anything else, in any position, is refused.
    """
    if not isinstance(function, str):
        raise RefusedQuery("the function must be a string")
    spec = FUNCTIONS.get(function.lower())
    if spec is None:
        raise RefusedQuery(f"{function!r} is not an RFC 8522 function this client sends")
    tail = _check_arg(spec.arg, arg, spec.name)
    pairs: list[tuple[str, str]] = []
    for name, value in query.items():
        lowered = name.lower()
        if lowered not in QUERY_PARAMETERS:
            raise RefusedQuery(f"{name!r} is not a query parameter of RFC 8522 sec. 2.2")
        if any(lowered == seen for seen, _ in pairs):
            raise RefusedQuery(f"{lowered} given twice")
        pairs.append((lowered, _query_value(lowered, value)))
    path = PREFIX + "/".join((*spec.segments, *tail))
    return ReadOnlyRequest(
        function=spec.name, path=path, query=tuple(sorted(pairs)), method="GET", _token=_TOKEN
    )
