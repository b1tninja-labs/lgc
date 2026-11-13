"""The read-only guard and the RFC 8522 request builder (RFC 8522 sec. 2, 3)."""

from __future__ import annotations

import dataclasses

import pytest

from lgc import guard, protocol
from lgc.guard import RefusedQuery, assert_read_only

# (function, argument, query, the request line printed in RFC 8522, section in brackets)
EXAMPLES = [
    (
        "ping",
        "2001:DB8::35",
        {"protocol": "2,1"},
        "/.well-known/looking-glass/v1/ping/2001:DB8::35?protocol=2,1",
    ),
    (
        "traceroute",
        "192.0.2.8",
        {"routerindex": 5},
        "/.well-known/looking-glass/v1/traceroute/192.0.2.8?routerindex=5",
    ),
    (
        "show route",
        "2001:DB8::/48",
        {"protocol": "2,1"},
        "/.well-known/looking-glass/v1/show/route/2001:DB8::/48?protocol=2,1",
    ),
    ("show bgp", "192.0.2.0/24", {}, "/.well-known/looking-glass/v1/show/bgp/192.0.2.0/24"),
    (
        "show bgp summary",
        None,
        {"protocol": 2, "routerindex": 3},
        "/.well-known/looking-glass/v1/show/bgp/summary?protocol=2&routerindex=3",
    ),
    (
        "show bgp neighbors",
        "192.0.2.226",
        {},
        "/.well-known/looking-glass/v1/show/bgp/neighbors/192.0.2.226",
    ),
    ("router details", 1, {}, "/.well-known/looking-glass/v1/routers/1"),
]


@pytest.mark.parametrize(("function", "arg", "query", "printed"), EXAMPLES)
def test_rfc8522_example_urls(function, arg, query, printed):
    request = assert_read_only(function, arg, **query)
    # Sec. 2 para 5: values are case insensitive, and this client sends the lower-case form.
    assert request.target == printed.lower()
    assert request.method == "GET"
    assert request.function == function


def test_function_syntax_lines_without_examples():
    # Sec. 3.3.1 and 3.3.3 syntax lines: .../v1/routers and .../v1/cmd.
    assert assert_read_only("router list").target == "/.well-known/looking-glass/v1/routers"
    assert assert_read_only("commands").target == "/.well-known/looking-glass/v1/cmd"


def test_the_allow_list_is_exactly_the_rfc_functions():
    assert set(guard.FUNCTIONS) == {
        "ping",
        "traceroute",
        "show route",
        "show bgp",
        "show bgp summary",
        "show bgp neighbors",
        "router list",
        "router details",
        "commands",
    }
    mandatory = {name for name, spec in guard.FUNCTIONS.items() if spec.mandatory}
    # Sec. 3.1.1 ping, 3.2.1 show route, 3.3 organizational commands "must be included".
    assert mandatory == {"ping", "show route", "router list", "router details", "commands"}
    assert guard.PREFIX == protocol.PREFIX == "/.well-known/looking-glass/v1/"


@pytest.mark.parametrize(
    "function",
    [
        "configure terminal",
        "show bgp ; reload",
        "show bgp\nreload",
        "show  bgp",
        " show bgp",
        "show ospf database",
        "reload",
        "clear ip bgp *",
        "",
        "show",
        "PING; reboot",
    ],
)
def test_allow_list_refuses_everything_else(function):
    with pytest.raises(RefusedQuery):
        assert_read_only(function, "192.0.2.1")


@pytest.mark.parametrize("function", [None, 5, b"ping", ["ping"]])
def test_function_must_be_a_string(function):
    with pytest.raises(RefusedQuery):
        assert_read_only(function, "192.0.2.1")


def test_function_names_are_case_insensitive_and_canonicalised():
    request = assert_read_only("SHOW BGP Summary")
    assert request.function == "show bgp summary"
    assert request.path == "/.well-known/looking-glass/v1/show/bgp/summary"


@pytest.mark.parametrize(
    "param", ["debug", "command", "cmd", "exec", "format;x", "Router2", "", "protocol "]
)
def test_unknown_query_parameter_refused(param):
    with pytest.raises(RefusedQuery):
        assert_read_only("show bgp summary", **{param: "x"})


def test_query_parameter_names_are_case_insensitive_and_sorted():
    request = assert_read_only("show bgp summary", RouterIndex=3, PROTOCOL="2")
    assert request.query == (("protocol", "2"), ("routerindex", "3"))
    with pytest.raises(RefusedQuery, match="twice"):
        assert_read_only("show bgp summary", protocol=1, PROTOCOL=2)


@pytest.mark.parametrize(
    "addr",
    [
        "192.0.2.0/24?x=1",
        "../../x",
        "a b",
        "1.2.3.4\r\nHost: evil",
        "%2e%2e",
        "192.0.2.1/24",  # host bits set
        "192.0.2.0/33",
        "2001:db8::/129",
        "192.0.2.0/",
        "192.0.2.0/-1",
        "fe80::1%eth0",
        "192.0.2.0/24/extra",
        "1.2.3",
        "256.1.1.1",
        "",
        " 192.0.2.1",
        "192.0.2.1;ls",
        "192.0.2.1#frag",
        chr(0x661) + ".2.3.4",
    ],
)
def test_addr_cannot_inject(addr):
    with pytest.raises(RefusedQuery):
        assert_read_only("show route", addr)


def test_argument_presence_matches_the_function():
    with pytest.raises(RefusedQuery, match="needs an argument"):
        assert_read_only("show route")
    with pytest.raises(RefusedQuery, match="takes no argument"):
        assert_read_only("show bgp summary", "192.0.2.1")
    with pytest.raises(RefusedQuery, match="takes no argument"):
        assert_read_only("commands", "x")
    with pytest.raises(RefusedQuery):
        assert_read_only("show bgp neighbors", "192.0.2.0/24")  # an address, not a prefix


@pytest.mark.parametrize(
    "host", ["example.net", "a-b.example.net", "EXAMPLE.net", "192.0.2.8", "2001:db8::1", "x"]
)
def test_host_arguments_accepted(host):
    assert assert_read_only("ping", host).path.startswith(guard.PREFIX + "ping/")


@pytest.mark.parametrize(
    "host",
    [
        "-a.example",
        "a..b",
        "a.",
        ".a",
        "a_b.example",
        "exa mple.net",
        "a/b",
        "a" * 64 + ".net",
        ("a." * 130) + "net",
        "1.2.3",
        "::g",
        "example.net/../x",
    ],
)
def test_host_arguments_refused(host):
    with pytest.raises(RefusedQuery):
        assert_read_only("ping", host)


@pytest.mark.parametrize("number", [-1, "-1", "abc", "1e3", 65536, 1.5, True, "", "1 2"])
def test_router_number_refused(number):
    with pytest.raises(RefusedQuery):
        assert_read_only("router details", number)


def test_router_number_accepted_forms():
    assert assert_read_only("router details", "07").path.endswith("/routers/7")
    assert assert_read_only("router details", 0).path.endswith("/routers/0")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("routerindex", -1),
        ("routerindex", "abc"),
        ("routerindex", 65536),
        ("routerindex", True),
        ("runtime", "abc"),
        ("runtime", "1e9"),
        ("runtime", 0),
        ("runtime", 3601),
        ("runtime", -5),
        ("random", "a b"),
        ("random", ""),
        ("random", "x" * 65),
        ("vrf", "a;b"),
        ("vrf", "-x"),
        ("router", "a b"),
        ("router", "a/b"),
        ("router", "x" * 300),
        ("router", "a&b=c"),
        ("format", "text"),
        ("format", "text/"),
        ("format", "/plain"),
        ("format", "text/plain;q=1"),
        ("format", ",text/plain"),
        ("format", ",".join(["text/plain"] * 9)),
        ("protocol", "x"),
        ("protocol", "2,"),
        ("protocol", ",1"),
        ("protocol", "1,2,3"),
        ("protocol", "65536"),
        ("protocol", "1,256"),
        ("protocol", "-1"),
        ("protocol", None),
    ],
)
def test_query_values_refused(name, value):
    with pytest.raises(RefusedQuery):
        assert_read_only("show bgp summary", **{name: value})


@pytest.mark.parametrize(
    ("name", "value", "sent"),
    [
        ("protocol", "2,1", "2,1"),
        ("protocol", "26", "26"),
        ("protocol", 2, "2"),
        ("routerindex", "8", "8"),
        ("runtime", 60, "60"),
        ("random", "517A93B50", "517A93B50"),
        ("vrf", "mgmt", "mgmt"),
        ("router", "rbgn06.example.net", "rbgn06.example.net"),
        ("format", "application/yang,text/plain", "application/yang,text/plain"),
        ("format", "text/x.netconf", "text/x.netconf"),
        ("format", "application/foo+json", "application/foo%2Bjson"),
    ],
)
def test_query_values_accepted_and_encoded(name, value, sent):
    request = assert_read_only("show bgp summary", **{name: value})
    assert request.query == ((name, sent),)


def test_protocol_afi_safi_syntax():
    for ok in ("2,1", "26", "1,1", "65535,255"):
        assert assert_read_only("show route", "192.0.2.0/24", protocol=ok)
    for bad in ("2,", "x", "2.1"):
        with pytest.raises(RefusedQuery):
            assert_read_only("show route", "192.0.2.0/24", protocol=bad)


def test_method_is_always_get():
    for function, arg, query, _ in EXAMPLES:
        assert assert_read_only(function, arg, **query).method == "GET"


def test_request_object_not_constructible_directly():
    with pytest.raises(TypeError, match="assert_read_only"):
        guard.ReadOnlyRequest(function="ping", path=guard.PREFIX + "ping/1.1.1.1", query=())
    with pytest.raises(TypeError, match="assert_read_only"):
        guard.ReadOnlyRequest(function="ping", path="/evil", query=(), _token=object())


def test_request_object_is_immutable():
    request = assert_read_only("show bgp summary")
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.path = "/evil"


def test_encode_request_is_the_guard():
    assert protocol.encode_request("show bgp", "192.0.2.0/24") == assert_read_only(
        "show bgp", "192.0.2.0/24"
    )
    with pytest.raises(RefusedQuery):
        protocol.encode_request("configure terminal")


def test_ipv6_is_emitted_in_canonical_lower_case():
    request = assert_read_only("show route", "2001:0DB8:0:0:0:0:0:0/32")
    assert request.path.endswith("/show/route/2001:db8::/32")
