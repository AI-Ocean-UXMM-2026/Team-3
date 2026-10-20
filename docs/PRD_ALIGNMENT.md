# PRD alignment for Phase 2

## Sources actually read

Read the full paragraph and table text from these DOCX files using their OOXML document
parts. The documents were not modified; this is a requirements comparison, not a layout review.

- `C:\Users\ZL_shit_H\Downloads\LannPya_AI_PRD_v2.docx` — version 2 PRD and strategic solutions.
- `C:\Users\ZL_shit_H\Downloads\Telegram Desktop\LannPya_PRD_Review.docx` — PRD review dated 20 October 2026.
- Another copy of `LannPya_AI_PRD_v2.docx` exists in Downloads/Telegram Desktop.

Search covered the project and accessible Documents, Downloads, and Desktop directories,
including matching filenames across extensions. No separate IA/information architecture
or use-case diagram was found. The PRD contains a textual system architecture/data flow;
that is not claimed to be a separate IA or diagram. Unrelated documents were not read.
The Phase 1 absence finding was limited to the project workspace and is superseded by
this wider discovery.

## Alignment and precedence

The PRD positions LannPya as middleware for shops and existing courier systems. Its
encoding → deterministic phone/COD → dictionary → AI assistance → triage pipeline
is consistent with the user's Phase 2 instructions. Its review emphasizes honest
limitations, human review, model-independent confidence, and transparent demo fallback.

| Requirement | Phase 1 contract | Phase 2 result |
| --- | --- | --- |
| Middleware, not a courier | Framework-independent REST foundation | Preserved; no courier actions implemented |
| Local encoding normalization | No extraction | Local detection, conversion, NFC, digit normalization, explicit warnings |
| Phone/COD deterministic; never AI-produced | Fixed null mock | Numbering-plan validation; explicit contextual whole-MMK rules |
| Controlled township dictionary | Null mock | Initial 33 curated Yangon names with spelling aliases and longest-match rules |
| Landmarks/floors/instructions | Null mock | Conservative labelled/bounded rules only; AI assistance deferred |
| Every field has source attribution | No extracted fields | All nine fields include status, method, rule, candidate evidence and verification metadata |
| Confidence from checks | Mock RED | Real RED/AMBER; GREEN requires trusted dataset evidence and no unresolved ambiguity |
| Human confirmation for unclear input | Mock reasons | Missing/invalid/competing candidates retain evidence and explicit confirmation reasons |
| Data minimization for AI | Replaceable mock interface | Preserved interface; no calls; fail-closed canonical-township-only context builder |
| Original-message highlighting | No original-message response | Exact original preserved; evidence offsets explicitly target normalized text |

## Explicit differences from the source PRD

The PRD mentions a specific AI model family, browser-side PII removal, a static SPA with
serverless API deployment, batch/CSV processing, confirmation links, and rider features.
The user's current instructions take precedence: retain Python/FastAPI, do not select a
real provider, apply data minimization on the server boundary, and implement single-order
deterministic parsing only. No browser edits, deployments, or out-of-scope features were made.

The PRD's map-match condition for GREEN cannot be inferred from an extracted road or
landmark. No reviewed location dataset was supplied or found in the project; the
default `LocationCatalog` therefore has no entries. The GREEN decision branch is
implemented and tested with synthetic fixtures, never presented as real map evidence.
Importing trustworthy township-scoped locations is a prerequisite to enabling GREEN.

## Implementation references

- [Myanmar Tools Python documentation](https://github.com/google/myanmar-tools/blob/master/clients/python/README.rst): local encoding detection; detector uncertainty is not delivery confidence.
- [Python Myanmar encoding documentation](https://python-myanmar.readthedocs.io/en/latest/converter.html): local converter API. Its output needs review; one vowel-order normalization is applied, not arbitrary spelling repair.
- [python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers): local numbering metadata; installed lightweight distribution omits unnecessary geocoder datasets.
- [MIMU place codes](https://www.themimu.info/place-codes): reference for future formal place dictionary work. The bundled initial alias file is hand-curated, not an imported MIMU geospatial dataset or claim of exhaustive current administrative coverage.

Phone reachability, AI accuracy, address geocoding, location ownership, completeness of
Myanmar coverage, and production security have not been established by this phase.
