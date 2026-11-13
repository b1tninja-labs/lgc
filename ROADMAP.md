# Specification completeness -- and the roadmap it implies

This is the project's north star: every protocol obligation lgc could plausibly take on,
with an honest status against the code at `HEAD`. It is blunt about gaps on purpose. A
roadmap that overstates its coverage is not a plan, it is marketing.

**The honesty rule:** a row may read `[ok]` only when a named test would fail if the
behaviour regressed. Reading the code and agreeing with it is not enough. That is how
"decoded but never sent" quietly becomes "implemented".

Legend: `[ok]` implemented and pinned by a named test -- `[part]` partial, with what is
missing stated -- `[ ]` not implemented -- `[no]` deliberate non-goal.

A Where cell marked `(to be written)` names the test that will pin the row once it exists; no
such test has been written yet, and the row cannot leave `[ ]` until it has. The Milestone
column places the row on the ladder in section 2, and `-` means it is not placed yet.

Update the affected row in the same commit that changes the behaviour. A row and its test
drift apart within one release, and the document becomes useless exactly when it is needed.

## 1. Obligations

| Obligation | Spec | Status | Where | Milestone |
|---|---|---|---|---|
| `guard.assert_read_only()` | RFC 8522 sec. 2 para 3, sec. 3 para 2: returns a GET request for an allow-listed function and refuses every function name, argument and query parameter outside the allow list | `[ok]` | `tests/test_guard.py::test_allow_list_refuses_everything_else` | M1 |
| `protocol.encode_request()` | RFC 8522 sec. 2, sec. 3: the same call as the guard, under the roadmap's name | `[ok]` | `tests/test_guard.py::test_rfc8522_example_urls` | M1 |
| `guard.functions` | RFC 8522 sec. 3: the nine functions and which are mandatory (ping, show route, router list, router details, commands) | `[ok]` | `tests/test_guard.py::test_the_allow_list_is_exactly_the_rfc_functions` | M1 |
| `guard.arguments` | RFC 8522 sec. 3.1 to 3.3: address, prefix, host name or router number per function; no injection through any of them | `[ok]` | `tests/test_guard.py::test_addr_cannot_inject` | M1 |
| `guard.query-parameters` | RFC 8522 sec. 2.2: the seven parameters and their value syntax; bounds not in the RFC are labelled conventions in `lgc/guard.py` | `[ok]` | `tests/test_guard.py::test_query_values_refused` | M1 |
| `guard.request-type` | the request object can be made only by the guard (RFC 8522 sec. 2 para 3 as a type) | `[ok]` | `tests/test_guard.py::test_request_object_not_constructible_directly` | M1 |
| `protocol.decode_response()` | RFC 8522 sec. 2.3 and Appendix A (JSend): the body decides the status, the HTTP code is compared and reported | `[ok]` | `tests/test_protocol.py::test_jsend_variants` | M2 |
| `protocol.decode-hostile-body` | RFC 8522 sec. 2.3: untrusted JSON (size, UTF-8, duplicate members, NaN, nesting) | `[ok]` | `tests/test_protocol.py::test_duplicate_keys_refused` | M2 |
| `finding.rfc8522-section-2-3-1-json` | RFC 8522 sec. 2.3.1: the printed example is not valid JSON (no comma after the router member) | `[ok]` | `tests/test_protocol.py::test_rfc8522_section_2_3_1_example_is_not_valid_json` | - |
| `finding.rfc8522-section-3-3-2-timing` | RFC 8522 sec. 3.3.2 against sec. 2.3.1: the router details example has no performed_at or runtime although sec. 2.3.1 says they must be present | `[ok]` | `tests/test_protocol.py::test_router_details_reply_has_no_timing_members` | - |
| `transport.call()` | RFC 8522 sec. 2 and sec. 6 para 1: HTTPS only; accepts a guarded request and nothing else; connect and total timeouts and a body cap (conventions, labelled as such); the response must be `application/json` (sec. 2.3 para 1) | `[ok]` | `tests/test_transport.py::test_budgets_enforced`, `tests/test_transport.py::test_response_rules` | M2 |
| `transport.no-redirect-no-proxy` | a 3xx is an error and the proxy environment variables are ignored (the stdlib `urllib` follows redirects and reads the environment; the HTTP/1.1 writer is the module's own) | `[ok]` | `tests/test_transport.py::test_redirect_not_followed` | M2 |
| `transport.guarded-request-only` | `call()` and `query_many()` cannot be invoked without a `ReadOnlyRequest` | `[ok]` | `tests/test_transport.py::test_only_guarded_request_accepted`, `tests/test_federation.py::test_federation_refuses_unguarded_queries_and_bad_bounds` | M2 |
| `transport.tls-trust` | RFC 8522 sec. 6 para 1 requires HTTPS; the default context verifies chain and host name, and a site may carry its own context to pin a private CA. No client certificate, no revocation checking, no TLS 1.3-only policy: say which are wanted | `[part]` | `tests/test_transport.py::test_untrusted_certificate_and_bad_sites` | M2 |
| `transport.http-framing` | the hand-written HTTP/1.1 reader accepts Content-Length, chunked and read-to-close bodies and refuses duplicate framing headers, content encodings and oversized headers; it does not speak HTTP/2 (RFC 8522 sec. 2.3.2 prints an `HTTP/2.0` example status line) | `[part]` | `tests/test_transport.py::test_budgets_enforced` | M2 |
| `sites.capability-discovery` | RFC 8522 sec. 3.3.1 `routers`, 3.3.2 `routers/{number}`, 3.3.3 `cmd`: `parse_router_list`, `parse_router_details`, `parse_commands`, `Capabilities.supports` and `discover` / `router_details` over the transport; what the server offers is information, and the guard still refuses anything off its own list | `[ok]` | `tests/test_sites.py::test_capability_discovery`, `tests/test_sites.py::test_malformed_router_details_are_refused`, `tests/test_sites.py::test_discover_asks_for_routers_and_cmd_and_router_details_by_number` | M2 |
| `finding.rfc8522-section-3-3-3-timing` | RFC 8522 sec. 3.3.3 against sec. 2.3.1: the commands example has no performed_at or runtime either, so `decode_response(function="commands")` relaxes the timing check as it does for router details | `[ok]` | `tests/test_sites.py::test_rfc8522_section_3_3_3_example_has_no_timing_members` | - |
| `finding.rfc8522-router-list-shape` | RFC 8522 sec. 3.3.1: the prose says the list includes "the router ID and its name", the example is an array of host names with no ids, and nothing ties a `routers/{number}` to a position in it. Only the array of strings is accepted; an array of objects is refused rather than guessed at. Ask the editors or find a real server before widening | `[ok]` | `tests/test_sites.py::test_malformed_lists_are_refused_and_failures_carry_no_listing` | - |
| `query.rib()` | RFC 8522 sec. 3.2.1: returns the raw `Success`, `Fail` or `Error` of `show route` for a prefix; no typed BGP objects | `[ok]` | `tests/test_query.py::test_rib_returns_the_raw_reply` | M1 |
| `query.detail()` | RFC 8522 sec. 3.2.2: the raw reply of `show bgp {prefix}` | `[ok]` | `tests/test_query.py::test_detail_returns_the_raw_reply` | M1 |
| `parsers.parse_rib()` | typed results from the `output` text. `pathattr`'s decoders (attributes, AS_PATH, communities, NLRI) read BGP wire octets, and RFC 8522 `output` is the router's printed text (sec. 2.3.1), so they have nothing to decode here; typing the text needs a vendor parser per command and version (next row). `pathattr` would apply only to a server offering a wire or YANG `format` (sec. 2.2), and no such server is known | `[ ]` | `tests/test_parsers.py::test_parse_rib` (to be written) | M3 |
| `parsers.per-device-fixtures` | one row per (vendor, version, command) with a captured fixture and a pinned version; the RFC 8522 `output` is whatever text the router printed (the sec. 3.2 examples are Cisco-style) | `[ ]` | `tests/test_parsers.py::test_cisco_show_bgp_fixture` (to be written) | M3 |
| `federation.query_many()` | not specified by RFC 8522 (sec. 1.1 only motivates several looking glasses; every sec. 2 call goes to one server): a convention of this client, one `SiteResult` per site with its own latency and error, a failure never changing another site's result, at most `MAX_CONCURRENT` sites at once | `[ok]` | `tests/test_federation.py::test_one_failure_is_isolated` | M5 |
| `transport.client-auth` | RFC 8522 sec. 6.2: requests may be authenticated by any method; which ones this client offers | `[ ]` | `tests/test_transport.py::test_client_auth` (to be written) | M4 |
| `transport.courtesy` | RFC 8522 sec. 6.1: servers may rate-limit; the client's own pacing and back-off are conventions | `[ ]` | `tests/test_transport.py::test_backoff` (to be written) | M4 |
| `transport.ssh` | SSH to a router or a looking glass: RFC 8522 sec. 2 para 3 forbids any direct client-to-router communication, the server-to-router protocol is unspecified (para 4), and neither the standard library nor `cryptography` has an SSH client | `[no]` | `tests/test_guard.py::test_the_allow_list_is_exactly_the_rfc_functions` | - |
| `transport.raw-tcp` | a raw TCP backend: no RFC 8522 function is defined over it | `[no]` | `tests/test_guard.py::test_the_allow_list_is_exactly_the_rfc_functions` | - |
| `guard.extension-commands` | RFC 8522 sec. 3.4 (for example `show/ospf/database`): server-defined, so a command nobody listed cannot be proved read-only | `[no]` | `tests/test_guard.py::test_allow_list_refuses_everything_else` | - |
| `devices.frr-bird-native` | the FRR and BIRD command interfaces (vtysh, the FRR REST API, birdc): not RFC 8522, which has the server talk to the router; a separate scope decision | `[no]` | `tests/test_guard.py::test_the_allow_list_is_exactly_the_rfc_functions` | - |
| `finding.rfc8522-federation` | RFC 8522 defines no federation, aggregation or multi-site behaviour (rfclib search, 2026-11-13: the only hit is sec. 1.1); the old row text "one reply per site" was this project's, not the RFC's | `[ok]` | `tests/test_federation.py::test_one_failure_is_isolated` | - |
| `interop.rfc8522-server` | find a non-Python RFC 8522 server to test against (publication checklist); none is named yet | `[ ]` | `tests/test_interop.py::test_against_a_real_server` (to be written) | M6 |

## 2. Milestones

- M1 the request builder and the read-only guard (done), and the query surface returning raw replies
- M2 the HTTPS transport, the response decoder (done) and capability discovery
- M3 typed results: parsers per device and version with captured fixtures, per-device text parsers with captured fixtures (`pathattr` decodes wire octets and does not apply to router text; see `parsers.parse_rib()`)
- M4 client authentication and pacing (RFC 8522 sec. 6.1, 6.2); the SSH backend this milestone used to carry is cut
- M5 multi site federation with per site accounting
- M6 publication: 0.1.0; the worked example composing rpkit state is contingent on rpkit having a stable API, which it does not

Every milestone is accepted by its rows above flipping to `[ok]` with a named test, not by
the code existing. Coverage in `pyproject.toml` ratchets in the same commit.

## 3. Errata watch

- RFC 8522 (Informational, independent stream, 2019-02) has no errata on file (rfclib, 2026-11-13). Its own examples carry two defects, pinned in `tests/test_protocol.py`: the sec. 2.3.1 example is not valid JSON, and the sec. 3.3.2 example lacks the members sec. 2.3.1 requires.
- RFC 4271 (Draft Standard) has 9 verified errata and is updated by RFC 4724, 6286, 6608, 6793, 7606, 7607, 7705, 8212, 8654, 9072, 9687 and 9774. Not read for this pass: it matters when typed parsing starts (M3), together with RFC 6793 (four-octet AS numbers), RFC 7606 and RFC 4760.
- RFC 8522 cites RFC 5785 for the well-known URI, which RFC 8615 obsoletes. The registered suffix `looking-glass` is unchanged by that.
- Vendor text formats change between releases without notice, which is why every parser needs a captured fixture per version.

## 4. Deliberate non-goals

| Non-goal | Status | Revisit when |
|---|---|---|
| a web front end or the RIB viewer itself; it returns objects you can render | `[no]` | a named document requires it |
| device configuration or any write path, ever | `[no]` | a named document requires it |
| generic network automation, which is scrapli, netmiko and napalm territory | `[no]` | a named document requires it |

## 5. Open questions

- typed results: `pathattr` is a declared dependency of asnkit, bmpkit, bgpfeed and routevalid in PORTFOLIO section 9 item 15, not of lgc. Checked 2026-11-13: the RFC 8522 `output` is router text, which `pathattr` does not decode, so `parsers.parse_rib()` needs it only for the objects it returns (an AS_PATH or community value type), not for decoding; the soft edge stays and the owner may drop it
- is there an RFC 8522 server to test against? The RFC is Informational and its sec. 1.1 background was not read in the first pass
- `guard.MAX_RUNTIME` and the other bounds in `lgc/guard.py` are conventions; whether any should be looser is for the first real user to say

## 6. Publication checklist

- [ ] every `[ ]` row above either `[ok]` or moved to a named later milestone
- [ ] `docs/research.md` claims re-verified and the dated ones either promoted or deleted
- [ ] interoperability evidence recorded in `docs/` against a non-Python implementation
- [ ] `tools/check_dist.py` proves the wheel ships the fixtures the README promises
- [ ] version 0.1.0 tagged, trusted publisher configured, README badges uncommented
