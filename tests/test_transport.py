"""The HTTPS backend against a local TLS server (RFC 8522 sec. 2.3, sec. 6 para 1).

Provenance: the server is an ``asyncio`` TLS listener on 127.0.0.1 with a self-signed certificate
minted here with ``cryptography`` (a dev dependency, never imported by the package). The JSON
bodies are the RFC 8522 sec. 2.3.1 and sec. 2.3.3 examples with the missing comma restored, so
the client is exercised against the RFC's own shapes and a real TLS handshake, not a mock.
"""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import json
import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lgc.guard import assert_read_only
from lgc.protocol import Error, ResponseError, Success
from lgc.transport import Budget, Site, TransportError, call

SUCCESS = json.dumps(
    {
        "status": "success",
        "data": {
            "router": "route-server.lookingglass.example.net",
            "performed_at": "2014-10-15T17:15:34Z",
            "runtime": 2.63,
            "output": ["full raw output from the observing router..."],
            "format": "text/plain",
        },
    }
).encode()
ERROR = json.dumps({"status": "error", "message": "Unrecognized host or address."}).encode()
REQUEST = assert_read_only("show bgp", "192.0.2.0/24")


@pytest.fixture(scope="module")
def tls(tmp_path_factory):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    directory = tmp_path_factory.mktemp("tls")
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server.load_cert_chain(cert_path, key_path)
    client = ssl.create_default_context(cafile=str(cert_path))
    return server, client


class Server:
    def __init__(self, handler):
        self.handler = handler
        self.requests: list[bytes] = []

    async def __aenter__(self):
        async def serve(reader, writer):
            try:
                head = await reader.readuntil(b"\r\n\r\n")
                self.requests.append(head)
                await self.handler(head, writer)
            except (ConnectionError, asyncio.IncompleteReadError, ssl.SSLError):
                pass
            finally:
                writer.close()

        self.server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=self.context)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()


def respond(body: bytes, *, status="200 OK", extra="", content_type="application/json"):
    async def handler(head, writer):
        text = f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\n{extra}"
        text += f"Content-Length: {len(body)}\r\n\r\n"
        writer.write(text.encode() + body)
        await writer.drain()

    return handler


async def run(tls, handler, *, budget=None):
    server_ctx, client_ctx = tls
    app = Server(handler)
    app.context = server_ctx
    async with app:
        site = Site("test", "127.0.0.1", app.port, ssl_context=client_ctx)
        try:
            return await call(site, REQUEST, budget), app
        finally:
            pass


async def test_budgets_enforced(tls):
    # a normal call: the guarded request goes out as one GET and the reply is decoded
    result, app = await run(tls, respond(SUCCESS))
    assert isinstance(result, Success)
    assert result.data["runtime"] == 2.63
    request = app.requests[0].decode()
    assert request.startswith(
        "GET /.well-known/looking-glass/v1/show/bgp/192.0.2.0/24 HTTP/1.1\r\n"
    )
    assert "Connection: close" in request
    error, _ = await run(tls, respond(ERROR, status="400 Bad Request"))
    assert isinstance(error, Error)
    assert error.http_consistent

    # total budget: a server that never answers
    async def silent(head, writer):
        await asyncio.sleep(5)

    with pytest.raises(TransportError, match="total time"):
        await run(tls, silent, budget=Budget(total_timeout=0.3))
    # body budget: declared length, then streamed length, then chunked length
    with pytest.raises(TransportError, match="body budget"):
        await run(tls, respond(SUCCESS), budget=Budget(max_body=20))

    async def endless(head, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n")
        for _ in range(50):
            writer.write(b"x" * 100)
            await writer.drain()

    with pytest.raises(TransportError, match="body budget"):
        await run(tls, endless, budget=Budget(max_body=1000))

    async def chunked(head, writer):
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        for piece in (SUCCESS[:10], SUCCESS[10:]):
            writer.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
        writer.write(b"0\r\n\r\n")
        await writer.drain()

    assert isinstance((await run(tls, chunked))[0], Success)
    with pytest.raises(TransportError, match="body budget"):
        await run(tls, chunked, budget=Budget(max_body=15))

    # header budget
    async def fat(head, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nX: " + b"a" * 5000 + b"\r\n\r\n")
        await writer.drain()

    with pytest.raises(TransportError, match="header too large"):
        await run(tls, fat, budget=Budget(max_header=1000))
    with pytest.raises(ValueError, match="positive"):
        Budget(total_timeout=0)


async def test_response_rules(tls):
    with pytest.raises(TransportError, match="application/json"):
        await run(tls, respond(SUCCESS, content_type="text/html"))
    with pytest.raises(ResponseError):
        await run(tls, respond(b'{"status":"success"}'))  # JSend needs data: never an empty result
    with pytest.raises(TransportError, match="content-encoded"):
        await run(tls, respond(SUCCESS, extra="Content-Encoding: gzip\r\n"))
    with pytest.raises(TransportError, match="status line"):
        await run(tls, lambda _head, writer: _raw(writer, b"garbage\r\n\r\n"))


async def _raw(writer, data):
    writer.write(data)
    await writer.drain()


async def test_redirect_not_followed(tls, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")  # ignored: nothing here reads it
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
    seen = []

    async def redirect(head, writer):
        seen.append(head)
        writer.write(
            b"HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1:1/elsewhere\r\n"
            b"Content-Type: application/json\r\nContent-Length: 0\r\n\r\n"
        )
        await writer.drain()

    with pytest.raises(TransportError, match="redirect"):
        await run(tls, redirect)
    assert len(seen) == 1  # no second request, to the Location or anywhere
    # and with the proxy variables set, a plain call still reaches the server directly
    result, _ = await run(tls, respond(SUCCESS))
    assert isinstance(result, Success)


async def test_only_guarded_request_accepted(tls):
    site = Site("test", "127.0.0.1", 1)
    for not_guarded in (
        "/.well-known/looking-glass/v1/ping/192.0.2.1",
        ("GET", "/x"),
        None,
    ):
        with pytest.raises(TypeError, match="ReadOnlyRequest"):
            await call(site, not_guarded)


async def test_untrusted_certificate_and_bad_sites(tls):
    server_ctx, _ = tls
    app = Server(respond(SUCCESS))
    app.context = server_ctx
    async with app:
        site = Site("test", "127.0.0.1", app.port)  # default context: the CA is not trusted
        with pytest.raises(TransportError, match="cannot connect"):
            await call(site, REQUEST)
    with pytest.raises(TransportError, match=r"cannot connect|connect timed out"):
        await call(Site("closed", "127.0.0.1", 1), REQUEST, Budget(connect_timeout=1))
    for bad in ("exa mple.org", "a\r\nb", "", "-x"):
        with pytest.raises(ValueError, match="host name"):
            Site("bad", bad)
    with pytest.raises(ValueError, match="port"):
        Site("bad", "example.org", 0)
    assert Site("v6", "2001:db8::1", 8443).host_header == "[2001:db8::1]:8443"
    assert Site("v4", "192.0.2.1").host_header == "192.0.2.1"
