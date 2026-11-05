"""the typed query surface: rib, ribin, ribout, detail, traceroute.

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    Site = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "detail",
    "rib",
]


async def rib(site: Site, prefix: str) -> list:
    """Pending behaviour defined by RFC 4271.

    Not implemented yet. See the ``query.rib()`` row in ROADMAP.md; this stub raises on
    purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("rib() is not implemented: RFC 4271")


async def detail(site: Site, prefix: str) -> list:
    """Pending behaviour defined by RFC 4271.

    Not implemented yet. See the ``query.detail()`` row in ROADMAP.md; this stub raises
    on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("detail() is not implemented: RFC 4271")
