"""The HTTPS backend with budgets (RFC 8522 sec. 6 para 1 requires HTTPS); SSH and raw TCP are not built.

``call`` sends one ``ReadOnlyRequest`` (only ``guard.assert_read_only`` makes one) to one site
and returns the decoded ``Success``, ``Fail`` or ``Error`` of ``protocol.decode_response``. The
HTTP/1.1 writer and reader are this module's own, on ``asyncio`` streams and ``ssl``, because the
standard library's ``urllib`` follows redirects and reads the proxy environment variables, and a
looking-glass client wants neither: a 3xx is an error, and no environment variable is read.

The limits below are conventions of this library, not RFC 8522 numbers: the RFC sets no timeout
and no size. Each is a field of ``Budget`` so a caller sets its own.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import re
import ssl
from dataclasses import dataclass, field

from .guard import ReadOnlyRequest
from .protocol import MAX_BODY, Error, Fail, Success, decode_response

__all__ = [
    "Budget",
    "Site",
    "TransportError",
    "call",
]

DEFAULT_PORT = 443
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
_CHUNK_SIZE_LINE = 64
_REDIRECT_MIN, _REDIRECT_MAX = 300, 399
_MAX_PORT = 65535


class TransportError(Exception):
    """The request did not produce a usable response: connection, timeout, redirect or framing."""


@dataclass(frozen=True, slots=True)
class Site:
    """One looking glass: where to connect, and the TLS context that decides whom to trust.

    ``ssl_context`` defaults to ``ssl.create_default_context()``, which verifies the server
    certificate and its name against ``host``. A caller pinning a private CA passes its own.
    """

    name: str
    host: str
    port: int = DEFAULT_PORT
    ssl_context: ssl.SSLContext | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        literal = False
        try:
            ipaddress.ip_address(self.host)
            literal = True
        except ValueError:
            pass
        if not literal and not _HOST.fullmatch(self.host):
            raise ValueError(f"{self.host!r} is not a host name or an IP address")
        if not 0 < self.port <= _MAX_PORT:
            raise ValueError("port must be 1..65535")

    @property
    def host_header(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port == DEFAULT_PORT else f"{host}:{self.port}"


@dataclass(frozen=True, slots=True)
class Budget:
    """Seconds and octets a call may spend. Conventions, not RFC 8522 numbers."""

    connect_timeout: float = 10.0
    total_timeout: float = 60.0
    max_body: int = MAX_BODY
    max_header: int = 16384

    def __post_init__(self) -> None:
        if min(self.connect_timeout, self.total_timeout, self.max_body, self.max_header) <= 0:
            raise ValueError("every budget must be positive")


async def call(
    site: Site, query: ReadOnlyRequest, budget: Budget | None = None
) -> Success | Fail | Error:
    """Send ``query`` to ``site`` over HTTPS and decode the reply (RFC 8522 sec. 2, 6).

    ``query`` must be a ``ReadOnlyRequest``: anything else, including a plain string, raises
    ``TypeError`` before a connection is made. The call is a single GET with ``Connection: close``;
    a redirect is not followed and raises ``TransportError``; the response must carry
    ``Content-Type: application/json`` (sec. 2.3 para 1), be unencoded, and fit ``budget``.
    ``TransportError`` also covers a connect or total timeout. A body that is not a valid RFC 8522
    reply raises ``protocol.ResponseError``, never an empty result.
    """
    if not isinstance(query, ReadOnlyRequest):
        raise TypeError("call() takes a ReadOnlyRequest made by lgc.guard.assert_read_only")
    budget = budget or Budget()
    try:
        async with asyncio.timeout(budget.total_timeout):
            status, headers, body = await _exchange(site, query, budget)
    except TimeoutError as error:
        raise TransportError("the call exceeded its total time budget") from error
    if _REDIRECT_MIN <= status <= _REDIRECT_MAX:
        raise TransportError(f"HTTP {status}: a redirect is an error and is not followed")
    media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media != "application/json":
        raise TransportError(
            f"Content-Type is {media!r}, RFC 8522 sec. 2.3 requires application/json"
        )
    return decode_response(status, body, function=query.function, max_body=budget.max_body)


async def _exchange(
    site: Site, query: ReadOnlyRequest, budget: Budget
) -> tuple[int, dict[str, str], bytes]:
    context = site.ssl_context or ssl.create_default_context()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(site.host, site.port, ssl=context, server_hostname=site.host),
            budget.connect_timeout,
        )
    except TimeoutError as error:
        raise TransportError("connect timed out") from error
    except (OSError, ssl.SSLError) as error:
        raise TransportError(f"cannot connect to {site.name}: {error}") from error
    try:
        request = (
            f"GET {query.target} HTTP/1.1\r\n"
            f"Host: {site.host_header}\r\n"
            "Accept: application/json\r\n"
            "Connection: close\r\n"
            "User-Agent: lgc\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await writer.drain()
        return await _read_response(reader, budget)
    except (OSError, ssl.SSLError, asyncio.IncompleteReadError) as error:
        raise TransportError(f"connection to {site.name} failed: {error}") from error
    finally:
        writer.close()
        with contextlib.suppress(OSError, ssl.SSLError):  # a close error after a read is not news
            await writer.wait_closed()


async def _read_head(reader: asyncio.StreamReader, limit: int) -> bytes:
    try:
        head = await reader.readuntil(b"\r\n\r\n")
    except asyncio.LimitOverrunError as error:
        raise TransportError("response header too large") from error
    if len(head) > limit:
        raise TransportError("response header too large")
    return head


async def _read_response(
    reader: asyncio.StreamReader, budget: Budget
) -> tuple[int, dict[str, str], bytes]:
    head = (await _read_head(reader, budget.max_header))[:-4].decode("latin-1")
    lines = head.split("\r\n")
    parts = lines[0].split(" ", 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/1.") or not parts[1].isdigit():
        raise TransportError("not an HTTP/1.x status line")
    status = int(parts[1])
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if not colon or not name or name != name.strip():
            raise TransportError("malformed response header")
        key = name.lower()
        if key in headers and key in {"content-length", "transfer-encoding", "content-type"}:
            raise TransportError(f"duplicate {key} header")
        headers[key] = value.strip()
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise TransportError("the response is content-encoded and none was requested")
    if "transfer-encoding" in headers:
        if headers["transfer-encoding"].lower() != "chunked" or "content-length" in headers:
            raise TransportError("unsupported or ambiguous Transfer-Encoding")
        return status, headers, await _read_chunked(reader, budget.max_body)
    if "content-length" in headers:
        text = headers["content-length"]
        if not text.isascii() or not text.isdigit():
            raise TransportError("malformed Content-Length")
        if int(text) > budget.max_body:
            raise TransportError("response body exceeds the body budget")
        return status, headers, await reader.readexactly(int(text))
    body = await reader.read(budget.max_body + 1)
    if len(body) > budget.max_body:
        raise TransportError("response body exceeds the body budget")
    return status, headers, body


async def _read_chunked(reader: asyncio.StreamReader, limit: int) -> bytes:
    body = bytearray()
    while True:
        line = (await reader.readuntil(b"\r\n"))[:-2]
        if len(line) > _CHUNK_SIZE_LINE:
            raise TransportError("chunk size line too long")
        try:
            size = int(line.split(b";", 1)[0].strip(), 16)
        except ValueError as error:
            raise TransportError("malformed chunk size") from error
        if size == 0:
            while (await reader.readuntil(b"\r\n")) != b"\r\n":  # trailers are read and dropped
                pass
            return bytes(body)
        if len(body) + size > limit:
            raise TransportError("response body exceeds the body budget")
        body += await reader.readexactly(size)
        if await reader.readexactly(2) != b"\r\n":
            raise TransportError("chunk not terminated by CRLF")
