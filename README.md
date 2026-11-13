# lgc

<!-- PyPI badges go live with the first release. Until then a version badge renders
     "no version" on the landing page, which reads as a defect rather than a date, so
     the badges stay commented out until the tag exists.
-->

**Pre-alpha.** The request builder, the read-only guard and the response decoder for RFC 8522 are
implemented and tested. The transport and the query surface still raise `NotImplementedError`, and
nothing returns typed BGP objects yet. Read [ROADMAP.md](ROADMAP.md) before depending on any of it.

lgc -- looking glass client that returns objects, not terminal text

The last mile of every looking glass is text: someone parses show ip bgp output with a regular expression written in a hurry. RFC 8522 (Looking Glass Command Set) defines a uniform HTTP and JSON interface to a looking glass, and Python has no client for it: the old looking-glass package died in 2019 and pybird only covers BIRD. lgc is a client library with one promise: it is read only by construction, which is the property that lets you point it at production. Typed objects from pathattr and asnkit are the goal for the router output, and until pathattr has a codec for them the replies are returned raw.

## The gap, with a date

PyPI was queried on 2026-11-05 for this name and for every neighbouring project. Landscape
claims rot quickly: two projects in this portfolio shipped within five days of the survey,
which is why the table below carries dates instead of adjectives.

| Project | Version | Last release | Why it is not this project |
|---|---|---|---|
| looking-glass | 1.0.4 | 2019-03-26 | a web visualisation tool, abandoned |
| pybird | 1.2.0 | 2023-02-08 | BIRD only, no typed BGP objects |
| lgc, birdc, frr, gobgp, quagga | - | - | all free on PyPI (2026-11-05) |

What this project intends to add:

- an RFC 8522 client with capability discovery, timeouts and an allow list of the functions the RFC defines
- parsers per device and version producing pathattr objects rather than strings (blocked on pathattr)
- route, BGP and per-prefix detail queries with one return type
- read only enforcement in the type system: a request can be built only by the guard, so a caller cannot send a configuration command by accident
- concurrent multi site queries with per site latency and error accounting

## Specification spine

Status and publication dates below were read from the RFC Editor record on 2026-11-05. A
section number is cited only where that section was read in full; everything else cites the
document, which is the honest grain size for a plan. See [docs/rfc-map.md](docs/rfc-map.md).

| Document | Status | Published | What it gives this project |
|---|---|---|---|
| RFC 8522 | Informational | 2019-02 | the looking-glass interface: GET requests under `/.well-known/looking-glass/v1/`, JSend JSON replies |
| RFC 4271 | Draft Standard | 2006-01 | the semantics every parser ultimately claims to render (typed results, not yet) |

### Errata watch

- RFC 8522 has no errata on file (2026-11-13); its sec. 2.3.1 example is not valid JSON and its sec. 3.3.2 example lacks members sec. 2.3.1 requires, both pinned in the tests.
- Router output formats are not specifications with errata: pin versions in fixtures and treat output drift as a bug in the parser, not the device.
- Vendor text formats change between releases without notice, which is why every parser needs a captured fixture per version.

## Module layout

| Module | Responsibility |
|---|---|
| `protocol` | RFC 8522 requests and JSend response decoding |
| `transport` | the HTTPS backend with budgets (SSH and raw TCP are cut: ROADMAP.md) |
| `parsers` | per vendor and version output conversion into typed objects |
| `query` | the typed query surface: rib, ribin, ribout, detail, traceroute |
| `sites` | registry of looking glasses with capabilities and health |
| `guard` | read only enforcement: the closed list of RFC 8522 functions and the only way to make a request |
| `federation` | concurrent queries across sites with per site accounting |

## What it does not do

- a web front end or the RIB viewer itself; it returns objects you can render
- device configuration or any write path, ever
- generic network automation, which is scrapli, netmiko and napalm territory


## Install

```bash
git clone https://github.com/b1tninja/lgc.git
cd lgc
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
```

Not published to PyPI yet. The name is reserved for this repository's trusted publisher at
the moment of the first release.

## Development

All four gates must pass, on Linux and Windows alike:

```bash
ruff check . && ruff format --check .
mypy lgc tests
pytest -q --cov
python -O -m pytest -q
```

The last line is the one that matters most in a protocol library. `-O` strips `assert`, and a
parser whose bounds checks were asserts stops being a parser under production flags. Wire
paths raise named exceptions; asserts belong in tests and nowhere else.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
