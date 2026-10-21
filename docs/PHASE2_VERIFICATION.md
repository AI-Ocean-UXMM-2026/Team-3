# Phase 2 implementation and verification

Verified locally on 20 October 2026 using Windows PowerShell, Python 3.14.7, and
`backend/.venv`. Phase 2 implements actual local extraction behind the existing endpoint.
No external AI service receives any data, and no database or frontend was changed.

## Document discovery and alignment

Found and read the version 2 PRD in Downloads and the PRD review in Downloads/Telegram
Desktop. No separate IA or use-case diagram was found in the project, Documents,
Downloads, or Desktop search. See [PRD_ALIGNMENT.md](PRD_ALIGNMENT.md) for exact source
paths, the comparison, and conflicts resolved in favor of the current user instructions.
In particular, no model named by the source PRD was selected or integrated.

## What was implemented

`POST /api/orders/parse` now uses `LANNPYA_PARSER_MODE=rules` by default. The request and
all existing response field names/types remain stable. The response has `is_mock=false`,
`provider=rules`, actual extracted values, validation reasons, and additive normalization,
source metadata, and original-message fields. Explicit `parser_mode=mock` preserves the
Phase 1 fixed output. All original 30 regression cases remain and run in that mode where
their assertions concern the mock provider. Health, CORS, error envelopes, provider
interfaces, and dependency injection remain functional.

| Stage | Actual behavior |
| --- | --- |
| Original text | Preserved exactly, including whitespace, in `original_text`; never persisted |
| Encoding | Local Myanmar Tools detector; local python-myanmar converter when Zawgyi is strongly indicated; NFC; one explicit vowel-order normalization |
| Encoding uncertainty | Explicit review warning for conversion; RED and warning for uncertain encoding or conversion failure; never claim universal font conversion |
| Digits | Myanmar ၀–၉ translated to ASCII 0–9 before extraction |
| Phones | Deterministic candidate rules plus local Myanmar mobile numbering metadata; normalize to domestic 09 format; preserve conflicting/invalid evidence |
| COD | Explicit COD context only, whole MMK, valid comma grouping, bounded amount; reject ambiguity, unsupported shorthand/expressions, known foreign currencies, and prepaid conflicts |
| Townships | Versioned controlled JSON dictionary of 33 initial Yangon names and explicit spelling aliases; longest overlap wins; no fuzzy geocoding |
| Other fields | Labelled customer names; bounded English/Burmese streets, proximity landmarks, floors/units, closed instruction patterns, and basic time expressions |
| Sources | Every address key has method/status/rule/evidence/verification metadata; offsets refer only to normalized text |
| Triage | Rule-based RED/AMBER/GREEN conditions with human-readable reasons, independent of AI |
| Privacy | No AI calls; fail-closed future-context builder copies only an allowlisted canonical township, excluding all free text and personal/order details |

The detector itself uses a bundled local statistical model; its internal encoding
probability is not returned as address confidence. Extraction, candidate selection,
amount parsing, dictionary matching, and triage rules are deterministic for a given
input and installed metadata version. No LLM opinions or fabricated percentages are used.

## Triage policy actually enforced

- RED: missing/invalid/competing phone or township, an invalid/conflicting explicit COD,
  uncertain encoding, or conversion failure. No automatic selection between multiple orders.
- AMBER: valid phone format and known township but location remains unverified, an
  optional field is ambiguous/invalid, or converted Zawgyi needs review.
- GREEN: the phone/township conditions plus a unique, township-scoped street or landmark
  match in a server-injected trusted catalog, with no unresolved ambiguity or normalization
  warning. Dataset/source provenance is returned for the match. It does not prove phone
  reachability, ownership, an exact building, or a delivery pin.

**No reviewed street/landmark location dataset was supplied or found.** The default
catalog is intentionally empty and never yields GREEN. The GREEN branch passes tests
using a synthetic fixture that is not loaded by the application. Extracting an informal
landmark never marks it verified. No coordinates or external geocoding calls are produced.

## Sample requests and actual responses

Complete, unabridged request/response bodies for five synthetic samples are in
[PHASE2_SAMPLE_RESPONSES.json](PHASE2_SAMPLE_RESPONSES.json), generated through the actual
FastAPI application by `backend/scripts/record_phase2_samples.py`, not handwritten fixtures.
The sample phone/contact data is for testing only, not a claim about a real recipient.

Example request:

```json
{"raw_text":"၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀"}
```

Actual response projection (selected keys; full metadata is in the JSON artifact):

```json
{
  "is_mock": false,
  "provider": "rules",
  "address": {
    "customer_name": null,
    "phone_number": "09791234567",
    "township": "Hlaing",
    "street": "ဗဟိုလမ်း",
    "landmark": null,
    "building_floor_unit": null,
    "cod_amount": 25000,
    "delivery_instructions": null,
    "time_window": null
  },
  "confidence": "AMBER",
  "original_text": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀",
  "normalized_text": "09791234567၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD 25000"
}
```

Additional actual API outcomes:

| Sample request text | Actual response outcome |
| --- | --- |
| `လှိုင်မြို့နယ် ဗဟိုလမ်း အဆွေတော်နား` | RED; Hlaing/street/landmark extracted; phone null; MISSING_PHONE_NUMBER |
| `09791234567, Hlaing to Bahan, COD 25000` | RED; township null; competing Hlaing/Bahan candidates retained; AMBIGUOUS_TOWNSHIP |
| `၀၉၇၉၁၂၃၄၅၆၇၊ လႈိင္ၿမိဳ႕နယ္၊ ဗဟိုလမ္း၊ အေဆြေတာ္နား` | Zawgyi converted; phone/Hlaing/street/landmark extracted; AMBER with ZAWGYI_CONVERSION_REVIEW |
| `09791234567, Kamaryut, 4th floor, room A3, 3 pm` | AMBER; floor/unit and time extracted; cod_amount null |

## Verification results

Final commands executed from `backend` using `.venv\Scripts\python.exe`:

| Command/check | Result |
| --- | --- |
| `-m pytest -q` | **131 passed in 1.91s**, no warnings; includes all 30 Phase 1 cases plus 101 new cases |
| `-m ruff check .` | All checks passed |
| `-m ruff format --check .` | 27 files already formatted |
| `-m pip check` | No broken requirements found |
| `scripts/smoke_http.py` | Passed against a real temporary Uvicorn loopback server |
| Live `GET /health` | 200; exact expected status/service body |
| Live parse with Unicode digits, valid phone, township, street, COD | 200; phone 09791234567, Hlaing, COD 25000, AMBER, is_mock=false |
| Live parse without phone | 200; actual extracted address and RED classification |
| Live blank-text parse | 422; validation error |
| `scripts/record_phase2_samples.py` | Five complete actual API response samples recorded |
| `-m pip wheel --no-deps --wheel-dir dist .` | Built successfully; bundled dictionary and final parser source bytes checked against the workspace |

The smoke script stopped the server it created. No persistent server was started.
The dependency lock was refreshed after installation. Python 3.11+ is declared compatible,
but only the installed Python 3.14 environment was tested.

Tests cover Unicode and ASCII digits; domestic/international/spaced/hyphenated mobile
numbers; missing/invalid/multiple contacts; unknown/competing/repeated townships; overlapping
aliases; street names that resemble township names; explicit COD; time/floor/ID/fee/price
numbers that must not become COD; malformed/huge amounts; currency/payment conflicts;
actual varied output; missing addresses; conflicting landmarks/floors/time expressions;
independent fixed Zawgyi examples; conversion failure/uncertainty; source offsets; trusted
catalog scoping; no provider call in rules mode; minimal AI payloads; malformed/oversized
requests; OpenAPI; CORS; and legacy mock-provider failure behavior.

Initial lint issues were formatting-only and were fixed. An initial live smoke run
successfully checked HTTP behavior but failed while printing Burmese through the Windows
cp1252 console; the script now configures UTF-8 output and passed on rerun. No unresolved
test or local-environment failure remains.

## Known limitations and unresolved work

- Initial township names/aliases are partial, hand-curated, and not a polygon/boundary
  dataset. Administrative splits, homonyms, and unlisted Myanglish variants need review.
- No trusted location data currently enables GREEN in the default application. This is
  an explicit data prerequisite, not permission to treat extracted landmarks as verified.
- Encoding detection and conversion are best effort, especially for short/mixed text,
  minority-language scripts, spelling errors, or legacy-font variants. Converted output
  always needs review. Tests do not establish corpus-wide accuracy.
- Phone validity means numbering-plan plausibility, not reachability or ownership;
  newly allocated numbers may need an updated metadata package. Labelled identifiers
  are excluded, but unlabelled numeric intent cannot always be determined.
- COD extraction requires explicit context. Bare amounts/prices/fees are not assumed
  to be COD. Shorthand such as 25k or 2 သိန်း, decimals, arithmetic, foreign currencies,
  and conflicts are not resolved automatically. Missing COD remains null, not zero.
- Pattern-based street/landmark/name extraction is deliberately narrow. Labelled fields
  should be separated with punctuation or newlines; arbitrary prose, multiple orders,
  complex instructions, and schedule ranges are not generally understood. Basic time
  strings are not a validated scheduling system.
- Evidence is not mapped back to original Zawgyi offsets. Frontends must highlight
  normalized text using code-point offsets rather than treating them as original/UTF-16
  positions. Original text and field evidence contain PII and should not be logged.
- The future AI context helper is an allowlist, not a general PII redactor. It sends no
  useful free-text fragments yet. Enabling a real provider requires a reviewed policy.
- No authentication, persistence, buyer confirmation actions, batching, map geocoding,
  public deployment, load testing, or production data-retention policy was introduced.

## Recommendations for Phase 3

1. Obtain a reviewed Yangon location catalog with stable place IDs, township scope,
   provenance, licensing, ambiguous-name handling, and clear criteria for enabling GREEN.
2. Assemble consented/anonymized real Burmese/Myanglish/Zawgyi examples with dispatcher
   labels to measure false positives and expand dictionaries/rules. Review currency,
   phone/contact ambiguity, administrative names, and encoding edge cases first.
3. Define a server-side fragment/minimization policy before choosing any external AI
   provider. Keep phone/COD extraction authoritative in rules, with source provenance and
   explicit review of any future AI-filled fields.
4. Agree the next phase's confirmation/security/data-retention requirements separately;
   the current implementation deliberately includes none of those systems.

Launch remains documented in [backend README](../backend/README.md). See the updated
[frontend API contract](API_CONTRACT.md) for integration and CORS details.
