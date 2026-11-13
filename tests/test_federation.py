"""query_many(): one failure never changes another site's result (a convention; RFC 8522 has no federation).

Provenance: three local TLS listeners (test_transport.py's server): one answers with the RFC 8522
sec. 2.3.1 example, one with garbage, and one port nothing listens on.
"""

from __future__ import annotations

import pytest
from test_transport import SUCCESS, Server, respond, tls  # noqa: F401

from lgc.federation import query_many
from lgc.guard import assert_read_only
from lgc.protocol import Success
from lgc.transport import Budget, Site

REQUEST = assert_read_only("show route", "192.0.2.0/24")


async def test_one_failure_is_isolated(tls):  # noqa: F811
    server_ctx, client_ctx = tls
    good, bad = Server(respond(SUCCESS)), Server(respond(b"not json"))
    for app in (good, bad):
        app.context = server_ctx
    async with good, bad:
        sites = [
            Site("bad", "127.0.0.1", bad.port, ssl_context=client_ctx),
            Site("good", "127.0.0.1", good.port, ssl_context=client_ctx),
            Site("untrusted", "127.0.0.1", good.port),  # default trust store: handshake fails
        ]
        results = await query_many(sites, REQUEST, Budget(total_timeout=10))
    assert [r.site.name for r in results] == ["bad", "good", "untrusted"]
    assert results[0].reply is None
    assert "JSON" in (results[0].error or "")
    assert isinstance(results[1].reply, Success)
    assert results[1].error is None
    assert results[2].reply is None
    assert results[2].error
    assert all(r.seconds >= 0 for r in results)


async def test_federation_refuses_unguarded_queries_and_bad_bounds():
    site = Site("x", "127.0.0.1", 1)
    with pytest.raises(TypeError, match="ReadOnlyRequest"):
        await query_many([site], "/.well-known/looking-glass/v1/ping/192.0.2.1")
    with pytest.raises(ValueError, match="max_concurrent"):
        await query_many([site], REQUEST, max_concurrent=0)
    assert await query_many([], REQUEST) == []
