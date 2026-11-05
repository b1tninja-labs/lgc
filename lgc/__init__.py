"""lgc -- looking glass client that returns objects, not terminal text.

The last mile of every looking glass is text: someone parses show ip bgp output with a
regular expression written in a hurry.
"""

from __future__ import annotations

from . import apps, cli, federation, guard, parsers, protocol, query, sites, transport
from .federation import query_many
from .guard import assert_read_only
from .parsers import parse_rib
from .protocol import decode_response, encode_request
from .query import detail, rib
from .transport import call

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "apps",
    "assert_read_only",
    "call",
    "cli",
    "decode_response",
    "detail",
    "encode_request",
    "federation",
    "guard",
    "parse_rib",
    "parsers",
    "protocol",
    "query",
    "query_many",
    "rib",
    "sites",
    "transport",
]
