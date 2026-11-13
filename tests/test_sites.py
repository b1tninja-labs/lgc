"""Capability discovery: the RFC 8522 sec. 3.3 replies read into typed objects.

Provenance: the three response bodies are the examples printed in RFC 8522 sec. 3.3.1, 3.3.2 and
3.3.3 (rfclib, read 2026-11-13). The sec. 3.3.3 example wraps its ``href`` values across lines with
a "[multiline]" mark; they are joined here, as the RFC says they are one string. ``discover`` runs
against the local TLS listener of test_transport.py.
"""

from __future__ import annotations

import json

import pytest
from test_transport import Server, tls  # noqa: F401

from lgc.protocol import ResponseError, Success, decode_response
from lgc.sites import (
    Capabilities,
    Command,
    RouterDetails,
    discover,
    parse_commands,
    parse_router_details,
    parse_router_list,
    router_details,
)
from lgc.transport import Site

SECTION_3_3_1 = json.dumps(
    {
        "status": "success",
        "data": {
            "routers": [
                "route-server.lookingglass.example.net",
                "customer-edge.lookingglass.example.net",
                "provider-edge.lookingglass.example.net",
            ],
            "performed_at": "2014-10-19T20:07:01Z",
            "runtime": 0.73,
        },
    }
).encode()

SECTION_3_3_2 = json.dumps(
    {
        "status": "success",
        "data": {
            "id": 1,
            "name": "customer-edge.lookingglass.example.net",
            "format": "text/plain,text/x.netconf",
            "country": "de",
            "autonomous_system": 64512,
        },
    }
).encode()

SECTION_3_3_3 = json.dumps(
    {
        "status": "success",
        "data": {
            "commands": [
                {
                    "href": "https://example.net/.well-known/looking-glass/v1/show/route",
                    "arguments": "{addr}",
                    "description": "Print records from IP routing table",
                    "command": "show route",
                },
                {
                    "href": "https://example.net/.well-known/looking-glass/v1/traceroute",
                    "arguments": "{addr}",
                    "description": "Trace route to destination host",
                    "command": "traceroute",
                },
            ]
        },
    }
).encode()


def reply(body, function=None):
    decoded = decode_response(200, body, function=function)
    assert isinstance(decoded, Success)
    return decoded


def test_rfc8522_section_3_3_3_example_has_no_timing_members():
    """The sec. 3.3.3 example lacks performed_at and runtime, like the sec. 3.3.2 one."""
    with pytest.raises(ResponseError, match="performed_at or runtime"):
        decode_response(200, SECTION_3_3_3)
    assert reply(SECTION_3_3_3, "commands").performed_at is None


def test_capability_discovery():
    names = parse_router_list(reply(SECTION_3_3_1))
    assert names == (
        "route-server.lookingglass.example.net",
        "customer-edge.lookingglass.example.net",
        "provider-edge.lookingglass.example.net",
    )
    details = parse_router_details(reply(SECTION_3_3_2, "router details"))
    assert details == RouterDetails(
        1,
        "customer-edge.lookingglass.example.net",
        ("text/plain", "text/x.netconf"),
        "de",
        64512,
        {},
    )
    commands = parse_commands(reply(SECTION_3_3_3, "commands"))
    assert commands[0] == Command(
        "show route",
        "https://example.net/.well-known/looking-glass/v1/show/route",
        "{addr}",
        "Print records from IP routing table",
    )
    caps = Capabilities(names, commands)
    assert caps.supports("show route")
    assert caps.supports("TRACEROUTE")
    assert not caps.supports("show bgp")  # not listed: the mandatory ones are not assumed either
    assert not caps.supports("reload")  # not a function the guard knows
    ospf = Command("show ospf database", "https://example.net/x", None, None)
    assert Capabilities(names, (*commands, ospf)).extensions() == (ospf,)
    assert not Capabilities(names, (ospf,)).supports("show ospf database")


def test_router_details_defaults_and_extra_members():
    body = json.dumps(
        {"status": "success", "data": {"id": 3, "name": "r3.example.net", "vendor": "Acme"}}
    ).encode()
    details = parse_router_details(reply(body, "router details"))
    assert details.formats == ("text/plain",)  # sec. 3.3.2: a missing format is text/plain
    assert details.country is None
    assert details.autonomous_system is None
    assert details.extra == {"vendor": "Acme"}


@pytest.mark.parametrize(
    "data",
    [
        {"name": "r.example.net"},  # no router index: the response "must contain" it
        {"id": "1", "name": "r.example.net"},
        {"id": True, "name": "r.example.net"},
        {"id": 1},
        {"id": 1, "name": ""},
        {"id": 1, "name": "r", "format": "text/plain,"},
        {"id": 1, "name": "r", "country": 44},
        {"id": 1, "name": "r", "autonomous_system": -1},
        {"id": 1, "name": "r", "autonomous_system": "64512"},
    ],
)
def test_malformed_router_details_are_refused(data):
    body = json.dumps({"status": "success", "data": data}).encode()
    with pytest.raises(ResponseError):
        parse_router_details(reply(body, "router details"))


def test_malformed_lists_are_refused_and_failures_carry_no_listing():
    def success(data):
        return reply(json.dumps({"status": "success", "data": data}).encode(), "commands")

    stamp = {"performed_at": "2018-01-01T00:00:00Z", "runtime": 0.1}
    for data in ({**stamp}, {**stamp, "routers": "r1"}, {**stamp, "routers": ["r1", 2]}):
        with pytest.raises(ResponseError):
            parse_router_list(success(data))
    # the sec. 3.3.1 prose says "router ID and its name"; objects are refused, not guessed at
    with pytest.raises(ResponseError):
        parse_router_list(success({**stamp, "routers": [{"id": 1, "name": "r1"}]}))
    for entries in (
        {},
        {"commands": {}},
        {"commands": ["show route"]},
        {"commands": [{"href": "https://example.net/x"}]},
        {"commands": [{"command": "ping"}]},
        {"commands": [{"command": "ping", "href": "h", "arguments": 3}]},
    ):
        with pytest.raises(ResponseError):
            parse_commands(success(entries))
    fail = decode_response(200, json.dumps({"status": "fail", "data": stamp}).encode())
    error = decode_response(500, json.dumps({"status": "error", "message": "x"}).encode())
    for bad in (fail, error):
        with pytest.raises(ResponseError, match="carries no listing"):
            parse_router_list(bad)
        with pytest.raises(ResponseError):
            parse_commands(bad)
        with pytest.raises(ResponseError):
            parse_router_details(bad)


async def test_discover_asks_for_routers_and_cmd_and_router_details_by_number(tls):  # noqa: F811
    server_ctx, client_ctx = tls

    async def handler(head, writer):
        line = head.split(b"\r\n", 1)[0].decode()
        path = line.split(" ")[1]
        body = {
            "/.well-known/looking-glass/v1/routers": SECTION_3_3_1,
            "/.well-known/looking-glass/v1/cmd": SECTION_3_3_3,
            "/.well-known/looking-glass/v1/routers/1": SECTION_3_3_2,
        }[path]
        text = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        writer.write(text.encode() + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        await writer.drain()

    app = Server(handler)
    app.context = server_ctx
    async with app:
        site = Site("lab", "127.0.0.1", app.port, ssl_context=client_ctx)
        caps = await discover(site)
        one = await router_details(site, 1)
    assert len(caps.routers) == 3
    assert caps.supports("show route")
    assert one.name == "customer-edge.lookingglass.example.net"
    sent = [r.decode().split("\r\n")[0] for r in app.requests]
    assert sent == [
        "GET /.well-known/looking-glass/v1/routers HTTP/1.1",
        "GET /.well-known/looking-glass/v1/cmd HTTP/1.1",
        "GET /.well-known/looking-glass/v1/routers/1 HTTP/1.1",
    ]
