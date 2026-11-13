# Where every claim in this repository comes from

| Document | Status | Published | Verified against the publisher record on |
|---|---|---|---|
| RFC 8522 Looking Glass Command Set | Informational (independent stream), current; no errata on file | 2019-02 | 2026-11-13 |
| RFC 4271 BGP-4 | Draft Standard, current; 9 verified errata; updated by RFC 4724, 6286, 6608, 6793, 7606, 7607, 7705, 8212, 8654, 9072, 9687, 9774 (M3, not read) | 2006-01 | 2026-11-13 |
| RFC 4760 Multiprotocol Extensions for BGP-4 | Draft Standard, current (sec. 3 para 5 read: AFI is 2 octets, SAFI 1 octet) | 2007-01 | 2026-11-13 |
| RFC 5785 well-known URIs | Obsolete, obsoleted by RFC 8615; cited by RFC 8522 | 2010-04 | 2026-11-13 |

RFC 8522 is the looking-glass interface this project targets (PORTFOLIO.md section 9 item 15,
decided 2026-11-13). "LGC and LGS" as a named protocol, and the FRR and BIRD command interfaces,
were listed here before with no document, version or fixture behind them; they are not specifications
of this project and are removed. See ROADMAP.md rows `devices.frr-bird-native` and `transport.ssh`.

Citation rules, in the order they most often get broken:

1. Cite the document. A secondary write-up is a lead, not a source.
2. A section number is cited only if that section was read in full.
3. Errata are checked at each milestone freeze, not once at the start.
4. Where a claim came from a body outside the RFC series, that body is named here.

Re-verify with the RFC library rather than memory: `info('RFCnnnn')` for current status, `errata('RFCnnnn')` for corrections, and `read('RFCnnnn', view='normative')` for the MUST and SHOULD statements that become obligation rows.

## What was read of RFC 8522

Sections 1.3, 2 (all of it, with 2.1 to 2.3.3), 3 (3.1 to 3.4 in full), 4, 5.1, 6 and Appendix A, through rfclib on 2026-11-13. Findings that corrected the research brief for this project:

- the router list is `/routers` (sec. 3.3.1), router details are `/routers/{number}` (sec. 3.3.2) and the command list is `/cmd` (sec. 3.3.3); the brief guessed `router/list`, `router/details` and `commands`
- `ping` is mandatory (sec. 3.1.1) as well as `show route`, and its argument may be a host name, not only an address; `traceroute` is optional
- the use of HTTPS is required (sec. 6 para 1)
- sec. 3 para 2: no function can modify the server's state, so every method is GET
- sec. 4 para 2: a client should rely on the body's `status`, not the HTTP code
- sec. 2.2: the `runtime` query parameter, when 0, disables the server's limit; the guard never sends it
