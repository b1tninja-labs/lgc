# Changelog

The format follows Keep a Changelog, and this project adheres to Semantic Versioning.

## Unreleased

### Added

- `guard`: the closed list of the nine RFC 8522 functions, argument and query-parameter validation, and `ReadOnlyRequest`, which only `assert_read_only` can make.
- `protocol`: `encode_request` (the guard under the roadmap's name) and `decode_response`, a strict JSend decoder returning raw `Success`, `Fail` or `Error`.
- tests pinning two defects in RFC 8522's own examples (sec. 2.3.1 is not valid JSON; sec. 3.3.2 lacks the timing members sec. 2.3.1 requires).

### Changed

- The target protocol is RFC 8522. The "LGC and LGS" protocol the README named had no source and is gone, and the SSH and raw TCP backends are cut (ROADMAP.md).
- `docs/plan.md` says wave 5 (the generated "wave 3" was stale) and records a soft dependency on pathattr for typed results.

Still stubs, raising `NotImplementedError`: `transport.call`, `query.rib`, `query.detail`, `parsers.parse_rib`, `federation.query_many`.

## 0.0.0 - 2026-11-05

### Added

- Package skeleton, obligation matrix and CI gates for lgc.
- `lgc.apps` namespace reserved for composition that is not protocol behaviour.
