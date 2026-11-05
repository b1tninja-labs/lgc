"""LGC and LGS framing, request types and progress reporting.

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    Query = Any  # placeholder: give it a real type in the milestone that needs it
    Response = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "decode_response",
    "encode_request",
]


def encode_request(query: Query) -> bytes:
    """Pending behaviour defined by design.

    Not implemented yet. See the ``protocol.encode_request()`` row in ROADMAP.md; this
    stub raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("encode_request() is not implemented: design")


def decode_response(raw: bytes) -> Response:
    """Pending behaviour defined by design.

    Not implemented yet. See the ``protocol.decode_response()`` row in ROADMAP.md; this
    stub raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("decode_response() is not implemented: design")
