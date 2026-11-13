"""rib() and detail(): the raw replies of RFC 8522 sec. 3.2 through the guard and the HTTPS client.

Provenance: the server is the local TLS listener of test_transport.py; the bodies are the RFC
8522 sec. 3.2.1 and sec. 3.2.2 example responses (the BGP one abbreviated), so what comes back is
compared with the RFC's own text. Nothing is parsed out of ``output``: it stays a list of lines.
"""

from __future__ import annotations

import json

import pytest
from test_transport import Server, respond, tls  # noqa: F401

from lgc.guard import RefusedQuery
from lgc.protocol import Error, Success
from lgc.query import detail, rib
from lgc.transport import Site

ROUTE = json.dumps(
    {
        "status": "success",
        "data": {
            "output": [
                "S   2001:DB8::/48 [1/0]",
                "     via FE80::C007:CFF:FED9:17, FastEthernet0/0",
            ],
            "format": "text/plain",
            "performed_at": "2018-06-11T17:13:39Z",
            "runtime": 1.39,
            "router": "c2951.lab.lg.example.net",
        },
    }
).encode()


async def serve(tls, body, status="200 OK"):  # noqa: F811
    server_ctx, client_ctx = tls
    app = Server(respond(body, status=status))
    app.context = server_ctx
    return app, client_ctx


async def test_rib_returns_the_raw_reply(tls):  # noqa: F811
    app, client_ctx = await serve(tls, ROUTE)
    async with app:
        site = Site("lab", "127.0.0.1", app.port, ssl_context=client_ctx)
        reply = await rib(site, "2001:DB8::/48", protocol="2,1")
    assert isinstance(reply, Success)
    assert reply.data["output"] == [
        "S   2001:DB8::/48 [1/0]",
        "     via FE80::C007:CFF:FED9:17, FastEthernet0/0",
    ]
    sent = app.requests[0].decode().split("\r\n")[0]
    assert (
        sent == "GET /.well-known/looking-glass/v1/show/route/2001:db8::/48?protocol=2,1 HTTP/1.1"
    )
    # the guard stands in front: a name outside RFC 8522 sec. 2.2 never leaves the client
    with pytest.raises(RefusedQuery):
        await rib(Site("lab", "127.0.0.1", 1), "192.0.2.0/24", command="reload")


async def test_detail_returns_the_raw_reply(tls):  # noqa: F811
    body = json.dumps({"status": "error", "message": "show bgp is not implemented"}).encode()
    app, client_ctx = await serve(tls, body, "400 Bad Request")
    async with app:
        site = Site("lab", "127.0.0.1", app.port, ssl_context=client_ctx)
        reply = await detail(site, "192.0.2.0/24")
    assert isinstance(reply, Error)  # optional function (sec. 3.2.2): the refusal is returned as is
    assert reply.message == "show bgp is not implemented"
    assert (
        app.requests[0]
        .decode()
        .startswith("GET /.well-known/looking-glass/v1/show/bgp/192.0.2.0/24 HTTP/1.1")
    )
