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
| `protocol.encode_request()` | design | `[ ]` | `tests/test_obligations.py::test_encode_request` (to be written) | M2 |
| `protocol.decode_response()` | design | `[ ]` | `tests/test_obligations.py::test_decode_response` (to be written) | M2 |
| `transport.call()` | design | `[ ]` | `tests/test_obligations.py::test_call` (to be written) | M2 |
| `parsers.parse_rib()` | RFC 4271 | `[ ]` | `tests/test_obligations.py::test_parse_rib` (to be written) | M3 |
| `query.rib()` | RFC 4271 | `[ ]` | `tests/test_obligations.py::test_rib` (to be written) | M1 |
| `query.detail()` | RFC 4271 | `[ ]` | `tests/test_obligations.py::test_detail` (to be written) | M1 |
| `guard.assert_read_only()` | design | `[ ]` | `tests/test_obligations.py::test_assert_read_only` (to be written) | M1 |
| `federation.query_many()` | design | `[ ]` | `tests/test_obligations.py::test_query_many` (to be written) | M5 |

## 2. Milestones

- M1 the query and result model plus read only enforcement
- M2 LGS and LGC transport with capability discovery
- M3 FRR and BIRD parsers with captured fixtures per version
- M4 SSH and HTTP backends with host key pinning
- M5 multi site federation with per site accounting
- M6 publication: 0.1.0 with a worked example composing rpkit state

Every milestone is accepted by its rows above flipping to `[ok]` with a named test, not by
the code existing. Coverage in `pyproject.toml` ratchets in the same commit.

## 3. Errata watch

- LGC, LGS, FRR and BIRD interfaces are not specifications with errata: pin versions in fixtures and treat output drift as a bug in the parser, not the device.
- Vendor text formats change between releases without notice, which is why every parser needs a captured fixture per version.

## 4. Deliberate non-goals

| Non-goal | Status | Revisit when |
|---|---|---|
| a web front end or the RIB viewer itself; it returns objects you can render | `[no]` | a named document requires it |
| device configuration or any write path, ever | `[no]` | a named document requires it |
| generic network automation, which is scrapli, netmiko and napalm territory | `[no]` | a named document requires it |

## 5. Open questions

- M4 (SSH and HTTP backends with host key pinning) has no row; transport.call sits on M2: add a pinning row on M4, or fold M4 into M2

## 6. Publication checklist

- [ ] every `[ ]` row above either `[ok]` or moved to a named later milestone
- [ ] `docs/research.md` claims re-verified and the dated ones either promoted or deleted
- [ ] interoperability evidence recorded in `docs/` against a non-Python implementation
- [ ] `tools/check_dist.py` proves the wheel ships the fixtures the README promises
- [ ] version 0.1.0 tagged, trusted publisher configured, README badges uncommented
