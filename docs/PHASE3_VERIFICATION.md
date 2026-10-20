# Phase 3 audit and AI integration verification

Verified locally on 20 October 2026, Windows PowerShell, Python 3.14.7, project-local
`backend/.venv`. The Phase 2 audit passed before implementation began. Phase 3 adds a
provider-neutral hybrid enrichment boundary; it does not activate a real AI service.

## Phase 2 audit completed first

Inspected the repository, README, frontend API contract, Phase 2 verification report,
parser/services/schemas/configuration, and previous tests. Ran the complete suite:
**131 passed in 1.83s**, with no warnings. Ran the original real-Uvicorn smoke check.

| Audit item | Observed result |
| --- | --- |
| Real extraction vs fixed mock | Rules endpoint returns actual input-derived values; original mock remains a separate explicit demo mode |
| Burmese digit normalization | ၀၉၇၉၁၂၃၄၅၆၇ becomes 09791234567; ၂၅၀၀၀ becomes integer COD 25000 |
| Phone validation | Myanmar mobile numbering metadata, domestic/international/spaced formats, invalid and competing numbers covered |
| COD context | Explicit payment context; unrelated time/floor/ID/fee/price numbers and malformed amounts do not become COD |
| Township | Controlled dictionary and explicit aliases, longest overlap handling, unknown/multiple area checks |
| RED / AMBER / GREEN | Missing/invalid critical fields RED; unverified locations AMBER; trusted-catalog GREEN branch passed isolated tests |
| Zawgyi | Local conversion works for fixed and generated examples; conversion review, uncertainty, and failure warnings covered |
| Live health / parsing / empty input | 200 / 200 with actual values / 422 |

No failing Phase 2 implementation was found. Missing capabilities were the previously
documented data/feature boundaries: no reviewed street/landmark catalog to enable GREEN
in the default application, narrow prose patterns, no real AI adapter, and a legacy
township-only AI context helper. This phase adds the useful sanitized fragment path;
it does not misrepresent missing geographic data or real-model availability.

## What was implemented

The default parser mode is now `hybrid`, using the same endpoint and request schema.
`rules` retains Phase 2 behavior and `mock` retains the Phase 1 fixed demo. The original
131 regression cases remain; their default-mode configuration assertion was updated
from rules to hybrid to match this deliberate change. Explicit rules/mock tests keep
their original extraction and failure assertions.

```text
POST /api/orders/parse
  -> preserve original; normalize encoding and digits
  -> deterministic phone/COD extraction + controlled township matching
  -> conservative fragment selection and server-side redaction
  -> ExtractionGateway (timeout, error mapping, bounded strict JSON)
       -> AddressExtractionProvider
            -> local MockExtractionProvider / DisabledExtractionProvider
            -> external adapters blocked before invocation
  -> validate every suggestion against sanitized input evidence
  -> merge only allowed missing fields; retain deterministic ambiguity
  -> deterministic triage + review flags
  -> original API fields plus additive AI availability/provenance
```

| Area | Implemented behavior |
| --- | --- |
| Standard interface | `AddressExtractionProvider.extract(SanitizedAddressInput, timeout_seconds=...)` returns JSON matching `AIExtractionResponse` |
| Adapter isolation | Only adapters know provider-specific request/response conventions; services depend on the interface and canonical schema |
| Strict output | Only landmark, building_floor_unit, delivery_instructions; strict types, no extra fields; each non-null suggestion has value, fragment_id, quote |
| Input privacy | Only useful bounded address fragments and a controlled canonical township; no full message, customer object, or source metadata |
| Redaction | Phone/name/COD evidence masked; reliably labelled names masked everywhere; numeric sequences/emails/URLs/handles masked; sensitive clauses omitted |
| Minimization | Already extracted notes/units not sent for unrelated missing fields; empty, unnecessary, and oversized clauses omitted |
| Grounding | Unique quote in the referenced sanitized fragment, value contained in quote, original normalized span must still match; no crossing a redacted span |
| Atomic merge | All suggestions checked before any merge; AI cannot supply/overwrite phone, COD, name, township, street, coordinates, or confidence |
| Ambiguity | AI cannot erase competing deterministic evidence; nullable address stays unresolved, with an explicitly labelled review-only suggestion |
| Provenance | AI-filled fields have method=ai, provider, requires_review=true and original normalized-text evidence; they stay unverified |
| Mock honesty | Local mock returns null values; even a misbehaving mock's suggestions are never merged |
| Failure behavior | Deterministic results retained; HTTP 200 with explicit AI status/reason, no private upstream messages, no invented replacement data |
| Dispatch review | AI-filled/suggested fields and AI failures set manual_review_required; corrections can be made locally/resubmitted as raw_text |

The Phase 1 `AddressProvider` interface remains exclusively for its visible fixed demo
and tests; it is not a route to an external service. The earlier minimal township-only
helper is preserved for compatibility. New enrichment uses its own sanitized schemas.

## Provider configuration and real keys

Configuration is server-side only. No provider selector, key, or trusted-location flag
is accepted in the browser's parse request.

| Environment setting | Default / accepted values |
| --- | --- |
| LANNPYA_PARSER_MODE | hybrid; also rules or mock |
| LANNPYA_AI_PROVIDER | mock; also disabled |
| LANNPYA_AI_TIMEOUT_SECONDS | 3.0; positive, finite, maximum 30 seconds |
| LANNPYA_AI_MAX_INPUT_CHARS | 2000; 128–4000 address-fragment characters |

Unknown providers fail configuration validation. `ai/factory.py` selects the registered
local implementation. Tests can inject a canonical adapter through the application
factory or the `get_extraction_provider` dependency without changing frontend endpoints
or service logic. Future adapters require registration in this factory/settings allowlist.

**No real API key is needed or read in this phase.** No vendor SDK was added. A future
external adapter would require a provider decision, its server-side key configuration,
an approved privacy policy, and explicit authorization to change the gateway's current
external-call block. Setting an arbitrary provider name/key cannot activate one now.
There are no paid calls, retries, external resources, deployments, or Git pushes.

## Timeout, validation, rate limits, and degradation

The gateway passes the configured timeout to the adapter and enforces an async deadline.
Transport-level timeout exceptions map to `timeout`; cancellation propagates correctly.
Future adapters must use cancellable async I/O and set transport/body limits themselves;
a Python async deadline cannot forcibly stop arbitrary blocking or cancellation-ignoring code.

Canonical response JSON is limited to 16,384 characters. Non-string responses, malformed
JSON, markdown fences, duplicate keys, non-JSON numeric constants, invalid types, unknown
fields, and ungrounded suggestions are rejected before merge. An empty valid object means
no suggestions, not invented data. No model-reported confidence is accepted.

Typed rate limits preserve bounded retry advice (1–86,400 seconds, otherwise null).
There is no automatic retry or duplicate provider call. Expected and unexpected provider
failures log only fixed event/status codes; exception repr, stack trace, customer text,
SDK headers, and API keys are not logged at this boundary. Client AI messages are canned.

Available statuses are `not_requested`, `mock`, `disabled`, `available`, `timeout`,
`rate_limited`, `invalid_response`, `unavailable`, and `privacy_blocked`. API details and
field meanings are documented in [API_CONTRACT.md](API_CONTRACT.md).

## Example input and actual outputs

Input used for live hybrid verification:

```json
{"raw_text":"09791234567, Hlaing, COD 25000, address: behind red gate"}
```

Actual default response projection (selected keys, not the complete response):

```json
{
  "is_mock": false,
  "provider": "rules",
  "address": {
    "customer_name": null,
    "phone_number": "09791234567",
    "township": "Hlaing",
    "street": null,
    "landmark": null,
    "building_floor_unit": null,
    "cod_amount": 25000,
    "delivery_instructions": null,
    "time_window": null
  },
  "confidence": "AMBER",
  "ai": {
    "status": "mock",
    "provider": "mock",
    "is_mock": true,
    "attempted": true,
    "message": "Mock AI adapter: AI-derived fields are unavailable; no simulated values were merged.",
    "retry_after_seconds": null,
    "applied_fields": [],
    "suggested_fields": []
  },
  "manual_review_required": true
}
```

The local adapter receives this minimized canonical input, without the recipient phone
or COD amount:

```json
{
  "township": "Hlaing",
  "fragments": [{"id":"fragment_0","text":"address: behind red gate"}],
  "requested_fields": ["landmark","building_floor_unit","delivery_instructions"]
}
```

[PHASE3_SAMPLE_RESPONSES.json](PHASE3_SAMPLE_RESPONSES.json) contains full actual API bodies
for six repeatable synthetic scenarios: default mock, disabled, timeout, rate limit,
malformed JSON, and a grounded merge through an **injected local test double**. That
last case returns `landmark=red gate`, `method=ai`, `requires_review=true`, and AMBER to
verify the merge path; it is explicitly labelled NOT_REAL_AI and is not a shipped model
adapter. All scenarios have `external_ai_called=false`.

## Final verification results

Commands ran from `backend` using `.venv\Scripts\python.exe`.

| Check | Actual result |
| --- | --- |
| Pre-development full audit suite | 131 passed in 1.83s, no warnings |
| Final `-m pytest -q` | **203 passed in 2.63s**, no warnings; 131 previous cases plus 72 new cases |
| `-m ruff check .` | All checks passed |
| `-m ruff format --check .` | 35 files already formatted |
| `-m pip check` | No broken requirements found |
| Editable installation | Updated local package to 0.3.0; no new runtime/dev dependency or provider SDK |
| `scripts/smoke_http.py` | Passed on a real loopback Uvicorn server in hybrid mode |
| `scripts/smoke_http.py --mode rules` | Passed on a separate real loopback server in pure rules mode |
| Live health | HTTP 200, exact expected status/service body |
| Live Burmese phone/COD extraction | HTTP 200; phone 09791234567, COD 25000, Hlaing, AMBER |
| Live missing phone / empty text | RED with HTTP 200 / HTTP 422 |
| Live hybrid assistance | HTTP 200, actual phone/COD preserved, ai.status=mock, no invented landmark |
| `scripts/record_phase3_samples.py` | Six full scenario responses recorded, no external AI calls |
| `-m pip wheel --no-deps --wheel-dir dist .` | 0.3.0 wheel built successfully |

New tests cover provider interface/mock behavior; configuration and dependency switching;
malformed/duplicate/oversized JSON; strict/forbidden output fields; actual and reported
timeouts; upstream rate limits; cancellation; private failure messages/logs; external-call
blocking; phone/name/email/URL/account/amount redaction; payload limits; Unicode/emoji
source offsets; ungrounded and partially invalid suggestions; protected values; retained
ambiguity; unavailable AI; trusted deterministic GREEN vs unverified/AI-assisted AMBER;
manual review flags; and backward-compatible core request/response behavior.

Initial formatting issues were fixed. All final checks above passed. Smoke servers were
stopped by their scripts, and no persistent server is left running. Only the installed
Windows/Python 3.14 environment was tested; declared Python 3.11+ support is not a tested matrix.

## Unresolved risks and limits

1. No reviewed location catalog is installed; default GREEN remains disabled. Synthetic
   test catalogs are not real geographic evidence and are never loaded by the app.
2. No real-model quality, cost, latency, quota, authentication, or network integration has
   been evaluated. Enrichment currently provides architecture and a local unavailable-value
   mock. Failure and successful-merge paths are tested with isolated local adapters.
3. Redaction is conservative but not universal PII recognition. Unlabelled names or private
   details within useful address prose can remain. Over-redaction can remove useful unit
   information. External activation needs corpus-based privacy review and policy approval.
4. Grounding prevents unsupported invented strings but does not establish semantic accuracy.
   Input can itself be wrong or malicious. Untrusted fragments cannot trigger tools/actions,
   and all AI-filled/suggested fields need dispatcher review. No automatic verification occurs.
5. Encoding conversion, dictionary coverage, phone metadata freshness, and narrow deterministic
   text patterns retain their Phase 2 limits. Uncertain/failed encoding blocks AI preparation.
6. No correction persistence/review-confirmation endpoint, authentication, retention policy,
   buyer links, rider queues, database, WebSockets, routing, tracking, or spatial memory exists.
   The current editable result/resubmitted-text workflow is not a stored order workflow.

An AI failure never creates geographic evidence. An independently trusted deterministic
street can retain GREEN, but the failure sets manual_review_required and is explicitly
reported. Any AI-filled or review-only suggestion prevents automatic GREEN.

The next real-provider phase needs an explicit provider decision, approved server-side
secrets/privacy/transport policy, reviewed location data, and a labelled anonymized sample
corpus. None of those external or production actions was performed here.

References used for implementation checks:
[Python async timeout/cancellation](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for),
[Pydantic strict validation](https://docs.pydantic.dev/latest/concepts/strict_mode/), and
[Python JSON decoding](https://docs.python.org/3/library/json.html#json.loads).
