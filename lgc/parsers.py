"""per vendor and version output conversion into typed objects.

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

__all__ = [
    "parse_rib",
]


def parse_rib(text: str, flavour: str) -> list:
    """Pending behaviour defined by RFC 4271.

    Not implemented yet. See the ``parsers.parse_rib()`` row in ROADMAP.md; this stub
    raises on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("parse_rib() is not implemented: RFC 4271")
