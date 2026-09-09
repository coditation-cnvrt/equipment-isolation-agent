# Public-source research and mock SIC/PSD for P&ID 2151

Researched 2026-09-08. Deliverables:

- [Mock SIC](mock_sic_pnid_2151.json)
- [Mock PSD](mock_psd_pnid_2151.json)
- Existing contextual reference: [mock FHR](mock_fhr_pnid_2151.json)

These are original, synthetic development examples. They are not approved site
standards, actual Operations declarations, or executable isolation instructions.
No approval identity or plant observation has been inferred from public guidance.
Their `mock-*-v0.1` schemas are fixture formats, not supported production contracts.

## What the public documents support

| Public primary source | Relevant location | Use in this work |
|---|---|---|
| [HSE HSG253: safe isolation](https://www.hse.gov.uk/pubns/priced/hsg253.pdf) | Paragraphs 167–180; Appendix 3, pp. 47–48 | Proving, monitoring and disposal review; public model checklists. Test criteria and intervals need a plant-specific basis. |
| [HSE HSG250: permit-to-work systems](https://www.hse.gov.uk/pubns/priced/hsg250.pdf) | Paragraphs 22–23; Figure 1, p. 24; Appendix 2 | Public permit-form example and supporting certificate concepts; useful references for document relationships and handover. |
| [OSHA 1910.147](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147) | (c)(4), (d)(5)–(6), (f)(3)–(4) | Energy-control records, verification, possible energy reaccumulation, individual group-lock participation and shift continuity. |
| [HSE shift handover](https://www.hse.gov.uk/humanfactors/topics/shift-handover.htm) | Key principles | Outgoing/incoming communication and cross-checking inform PSD handover fields. |
| [NIOSH: carbon dioxide](https://www.cdc.gov/niosh/npg/npgd0103.html) | Exposure limits, IDLH and symptoms | CO2 has specific exposure hazards. Exposure-limit data are not an automatic entry, gas-free or hot-work acceptance criterion. |
| [HSE CO2 pipeline guidance](https://www.hse.gov.uk/pipelines/co2conveying-full.htm) | Corrosion, composition and release modelling | Composition and phase behavior need review; applicability to this equipment must be established separately. |

The isolation/proving checklists and permit example are publicly available
analogues. The sources reviewed do not establish our exact SIC/PSD JSON formats.
Those names, six PSD sections, field enums and HSC×EC matrix come from the project's
[requirements](isolation-planning-agent-ux-i1/extracted/Isolation_Planning_Agent_Requirements_v1.md),
sections 5.3, 5.4, 5.8 and 6.2–6.5. Public UK/US sources do not establish the governing
jurisdiction or approve a client-specific policy. Search also surfaced third-party
copies of company procedures; these were not used as authoritative inputs.

## SIC choices and limits

The fixture contains the requested barrier, escalation, matrix, proving, gas-test,
purge, tagging, electrical, permit, mode and export groups. `parameter_provenance`
separates four origins: project proposals, guidance-informed mock choices,
synthetic product choices and deliberately unresolved parameters.

DN50, seven-day escalation, thirty-day positive-isolation duration and twenty-four-
hour PSD validity are copied from the local requirements as proposed defaults.
They are not presented as universal HSE or OSHA requirements. The exact 16-cell
matrix remains referenced to the local specification and existing domain function;
no public-standard equivalence is asserted and no override is invented.

Check-valve exclusion, actuated-valve exclusion and the soft-seat flag are explicit
unapproved test selections. Null proving durations, leakage acceptance, gas-test
limits and purge settings exercise missing-input behavior. In particular, HSG253
paragraphs 174 and 180 describe risk/procedure-specific monitoring and proving
criteria rather than supplying one universal number. The mock does not turn the
presence of a gauge or an assumed vent into a verified isolation.
[Source: HSG253](https://www.hse.gov.uk/pubns/priced/hsg253.pdf).

There is no generated permit, emergency activation, electrical assessment, approved
tag colour scheme or purge recipe. The omission is represented as data, not an
implicit permission. UnknownFluid reduction, overlap precedence, bleed topology,
fallback strength and other architecture decisions remain listed as unresolved.

## PSD scenario and identities

The scenario uses the service vocabulary already recorded in the mock FHR:
CDH, PC, SWS, SWR and VRP, around the compressor discharge cooler and knockout
vessel. Project 277, collection 206, UniGraph project 21 and drawing/job 2151 are
copied from that fixture, not independently reconciled against a live graph.

Every equipment/header/valve identifier begins `MOCK-2151-`; graph IDs are null.
The equipment descriptions and service assignments are contextual hypotheses.
They do not establish physical connections, equipment identity, fluid composition,
valve availability or a real header destination.

The baseline has stopped equipment and live surrounding services, with explicitly
invented pressure/temperature values. VRP pressure and temperature remain unknown.
The six sections follow the project requirement: header, equipment state, system
status, valve-position exceptions, active isolations and active overrides.
`section_coverage` distinguishes unreviewed empty registers from a confirmed empty
inventory. Declarer and handover identities are fictional and unverified.

Fixed timestamps allow deterministic testing. The illustrative validity interval
is 2026-09-08 06:00 UTC to 2026-09-09 06:00 UTC; it is not refreshed to the current
clock. All values still need real Operations declarations and field confirmation.

Embedded scenarios specify row overrides or whole-section replacements:

1. Expired declaration.
2. Declared zero pressure without field verification.
3. Missing live-side pressure.
4. Vent declared out of service without demonstrated disposal suitability.
5. A valve-position exception with unresolved identity.
6. Unverified existing isolation and SIF override references.
7. Empty registers whose review is incomplete.

These are fixture transformations, not RFC 6902 patches or implemented runtime
behavior. Expected results are test intentions. Every scenario remains synthetic
and must fail production admission; none authorises an HSC reduction or establishes
a barrier, safe destination, executed isolation or an applied inhibit.

## Consequences for B1 implementation

Use these examples to build strict parsers and negative tests. Support nullable
unknown values without coercing them to zero, stable row identity, declared units,
explicit UTC timestamps, register coverage, provenance and an immutable snapshot.
Do not mix source provenance with a server-owned approval decision.

The fixtures do not resolve the graph snapshot contract, authorised approver,
complete SIC policy, exact scope hierarchy or plant identity mapping. Keep those
activation gates. Formal SIC base/delta composition and runtime SafetyContext work
remain pending; this research pass adds input examples, not a new admission mode.

No application code, migration, API/OpenAPI, UI or viewer changed in this research
slice. JSON syntax, source-reference integrity, context/service alignment and
synthetic status/identity checks were run locally. Existing worktree changes were
preserved; nothing was committed or pushed.
