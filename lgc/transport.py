"""HTTP, SSH and raw TCP backends with budgets and host keys.

Every object in this module is a placeholder until the milestone named in ROADMAP.md lands. A
stub raises instead of returning a plausible empty value: a protocol library that silently
answers nothing is worse than one that refuses to answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    Budget = Any  # placeholder: give it a real type in the milestone that needs it
    Query = Any  # placeholder: give it a real type in the milestone that needs it
    Response = Any  # placeholder: give it a real type in the milestone that needs it
    Site = Any  # placeholder: give it a real type in the milestone that needs it

__all__ = [
    "call",
]


async def call(site: Site, query: Query, budget: Budget) -> Response:
    """Pending behaviour defined by design.

    Not implemented yet. See the ``transport.call()`` row in ROADMAP.md; this stub raises
    on purpose so nothing downstream mistakes it for working code.
    """
    raise NotImplementedError("call() is not implemented: design")
