"""RFC 8522 requests and responses: build a GET request, decode the JSend reply.

A request is built by ``guard.assert_read_only`` (``encode_request`` is the same call under the
name the roadmap uses). A response is the JSON body RFC 8522 sec. 2.3 describes, in the JSend shape
of its Appendix A: ``status`` is ``success``, ``fail`` or ``error``. Results stay raw: ``data`` is
the server's JSON object as sent, and the typed accessors read only the members sec. 2.3.1 names.
Turning ``output`` text into BGP objects is a parser's job and waits on ``pathattr``
(ROADMAP.md).

The body is untrusted input. It is size-checked before it is parsed, decoded as strict UTF-8,
and parsed with duplicate member names and ``NaN``/``Infinity`` refused.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Literal

from .guard import PREFIX, ReadOnlyRequest, assert_read_only

__all__ = [
    "MAX_BODY",
    "PREFIX",
    "Error",
    "Fail",
    "ResponseError",
    "Success",
    "decode_response",
    "encode_request",
]

MAX_BODY = 1_048_576
"""Largest response body ``decode_response`` parses. A convention: RFC 8522 sets no size."""


_UNTIMED = frozenset({"router details", "commands"})
"""Replies whose RFC 8522 example has no ``performed_at`` or ``runtime`` (sec. 3.3.2, 3.3.3)."""


class ResponseError(ValueError):
    """The body is not a valid RFC 8522 response. The message says which rule it broke."""


def encode_request(
    function: str, arg: str | int | None = None, **query: str | int
) -> ReadOnlyRequest:
    """Build the GET request for an RFC 8522 function (RFC 8522 sec. 2, sec. 3); see ``guard``.

    ``encode_request("show bgp", "192.0.2.0/24")`` is the sec. 3.2.2 example,
    ``/.well-known/looking-glass/v1/show/bgp/192.0.2.0/24``. Anything outside the allow list
    raises ``guard.RefusedQuery``.
    """
    return assert_read_only(function, arg, **query)


@dataclass(frozen=True, slots=True)
class _Reply:
    """What every status shares: the raw ``data`` object and the HTTP status it arrived with."""

    data: dict[str, Any]
    http_status: int

    @property
    def router(self) -> str | None:
        value = self.data.get("router")
        return value if isinstance(value, str) else None

    @property
    def performed_at(self) -> datetime.datetime | None:
        value = self.data.get("performed_at")
        return _utc(value) if isinstance(value, str) else None

    @property
    def runtime(self) -> float | None:
        value = self.data.get("runtime")
        return (
            float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
        )

    @property
    def format(self) -> str:
        """The format the server chose; ``text/plain`` when it said nothing (sec. 2.3.1 para 6)."""
        value = self.data.get("format")
        return value if isinstance(value, str) else "text/plain"

    def lines(self) -> tuple[str, ...]:
        """``output`` as lines: a list of strings as sent, or one string as a single line.

        Blank or absent output is an empty tuple (sec. 2.3.1 para 5 allows it). Any other JSON
        type (a structured format such as ``application/yang``) is not text and raises; read
        ``data["output"]`` for it.
        """
        value = self.data.get("output")
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value)
        raise ResponseError("output is not text: read data['output'] directly")


@dataclass(frozen=True, slots=True)
class Success(_Reply):
    """``status: "success"``: the command ran and worked (RFC 8522 sec. 2.3.1)."""

    status: Literal["success"] = "success"

    @property
    def http_consistent(self) -> bool:
        return self.http_status == 200


@dataclass(frozen=True, slots=True)
class Fail(_Reply):
    """``status: "fail"``: the command ran on the router and failed (sec. 2.3.2)."""

    status: Literal["fail"] = "fail"

    @property
    def http_consistent(self) -> bool:
        return self.http_status == 200


@dataclass(frozen=True, slots=True)
class Error:
    """``status: "error"``: a timeout or a processing error (sec. 2.3.3)."""

    message: str
    code: int | float | None
    data: dict[str, Any] | None
    http_status: int
    status: Literal["error"] = "error"

    @property
    def http_consistent(self) -> bool:
        """400, 500, 502 and 504 are the codes sec. 2.3.3 para 3 names ("should")."""
        return self.http_status in (400, 500, 502, 504)


def _utc(text: str) -> datetime.datetime:
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError as error:
        raise ResponseError(f"performed_at {text!r} is not ISO 8601") from error
    if moment.tzinfo is None or moment.utcoffset() != datetime.timedelta(0):
        raise ResponseError(f"performed_at {text!r} is not UTC")
    return moment


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ResponseError(f"duplicate member name {key!r}")
        out[key] = value
    return out


def _refuse_constant(name: str) -> Any:
    raise ResponseError(f"{name} is not a JSON value")


def _check_data(data: object, *, timing: bool) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ResponseError('"data" must be an object')
    if timing and ("performed_at" not in data or "runtime" not in data):
        raise ResponseError("data lacks performed_at or runtime (RFC 8522 sec. 2.3.1 para 2-3)")
    if "performed_at" in data:
        if not isinstance(data["performed_at"], str):
            raise ResponseError("performed_at must be a string")
        _utc(data["performed_at"])
    if "runtime" in data:
        runtime = data["runtime"]
        if isinstance(runtime, bool) or not isinstance(runtime, int | float) or runtime < 0:
            raise ResponseError("runtime must be a non-negative number of seconds")
    for key in ("router", "format"):
        if key in data and not isinstance(data[key], str):
            raise ResponseError(f"{key} must be a string")
    return data


def decode_response(
    status_code: int,
    body: bytes,
    *,
    function: str | None = None,
    max_body: int = MAX_BODY,
) -> Success | Fail | Error:
    """Decode an RFC 8522 response body into ``Success``, ``Fail`` or ``Error`` (sec. 2.3, Appendix A).

    The body's ``status`` decides, not the HTTP status code (sec. 4 para 2 says to rely on the
    field); the pair is compared and ``http_consistent`` reports a disagreement instead of hiding
    it. ``success`` and ``fail`` need ``data`` with ``performed_at`` (UTC) and ``runtime``;
    ``error`` needs ``message``. Pass ``function="router details"`` or ``function="commands"``
    for those replies, whose sec. 3.3.2 and sec. 3.3.3 examples carry neither timing member
    although sec. 2.3.1 says they must be present. Raises ``ResponseError`` for anything else, never an empty result.
    """
    if not isinstance(body, bytes | bytearray):
        raise TypeError("decode_response takes the body as bytes")
    if len(body) > max_body:
        raise ResponseError(f"body is {len(body)} bytes, over the {max_body} limit")
    try:
        text = bytes(body).decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_refuse_constant)
    except UnicodeDecodeError as error:
        raise ResponseError("body is not UTF-8") from error
    except (json.JSONDecodeError, RecursionError) as error:
        raise ResponseError(f"body is not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ResponseError("body must be a JSON object")
    status = parsed.get("status")
    timing = function not in _UNTIMED
    if status in ("success", "fail"):
        if "data" not in parsed:
            raise ResponseError(f'status "{status}" needs "data" (JSend, RFC 8522 Appendix A)')
        data = _check_data(parsed["data"], timing=timing)
        cls = Success if status == "success" else Fail
        return cls(data=data, http_status=status_code)
    if status == "error":
        message = parsed.get("message")
        if not isinstance(message, str) or not message:
            raise ResponseError('status "error" needs a "message" string (sec. 2.3.3 para 1)')
        code = parsed.get("code")
        if code is not None and (isinstance(code, bool) or not isinstance(code, int | float)):
            raise ResponseError("code must be a number")
        detail = _check_data(parsed["data"], timing=False) if "data" in parsed else None
        return Error(message=message, code=code, data=detail, http_status=status_code)
    raise ResponseError(f'status must be "success", "fail" or "error", got {status!r}')
