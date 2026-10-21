# Phase 16 — local MVP completion

Executed 2026-10-21 on `integration/lannpya-final`. Existing uncommitted Phase 15 work was
preserved. No original development branch, production data, remote repository or deployment
was modified. No real-model call or paid service was activated.

## Completed functionality

**Customer map:** locally vendored Leaflet 1.9.4 supports clicking/dragging a pin, coordinate
editing and browser geolocation with denial handling. The initial Yangon viewport is only
an overview: no marker or customer coordinates are invented. Selection is local until the
verified buyer submits through the existing protected API. Initial pins remain proposals;
the canonical order is unchanged until dispatcher approval. Approved coordinates persist
and reach rider navigation. Existing server-side trusted-reference/500-meter and township
policies remain authoritative; unverified pins do not become GREEN.

Street tiles are off until the buyer requests them. The UI explains external map contact.
Only the fixed OSM tile image origin was added to CSP; scripts/API calls remain same-origin.
Requests use origin-only Referer, normal browser caching and visible attribution, consistent
with the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/). Private
buyer links, credentials, phone and notes are not sent. Tile failure leaves coordinate
selection available. Browser tests intercept tiles; external service availability was not
tested. No bulk tile fetching or offline tile archive was implemented.

**History:** protected order details now load all pages of actual persisted events and show
them chronologically with Yangon timestamps. Status, buyer request/review, rider assignment
and completion events appear. Arbitrary metadata, private submitted values and actor IDs
are excluded. Empty/error/retry states are explicit; history failure does not hide the
saved order. Navigation-generation guards prevent stale history responses crossing orders.

## Files and architecture

- Frontend: `customer-map.js`, vendored Leaflet JS/CSS/license, `api-workspace.mjs`, `api.css`,
  `index.html`, `api.html`. Existing vanilla JavaScript, styling and workflow controls remain.
- Local shell: fixed tile-image CSP origin in `tools/backend_test_dashboard/server.py`;
  cookie, CSRF, loopback and role protection remain intact.
- AI: `app/ai/adapters/http.py`, factory/gateway/config/hybrid wiring and `.env.example`.
  No provider SDK, endpoint rename, response-schema break or migration was required.
- Tests/evidence: `tests/browser/phase16.spec.cjs`, two Node history regressions,
  `backend/tests/test_phase16_ai.py`, `tests/fixtures/phase16_ai_benchmark.json`,
  `tools/evaluate_ai_readiness.py` and `docs/phase16/` evidence files.

## Verification

| Check | Actual result |
| --- | --- |
| Complete Python suite | **870 passed**, 96.82s |
| Final affected AI/hybrid recheck | **100 passed**, including 28 new AI tests |
| Node frontend | **98 passed** |
| Retained dashboard / HTTP integration | **17 + 1 passed** |
| TypeScript parser | **141 passed**, nine files; type-check passed |
| Real Chromium | **33 passed**, all original 28 plus five new cases |
| Ruff / formatting | Passed; 105 Python files formatted |
| Build | 24 validated static assets, JS syntax/import checks passed |
| Dependencies | pip check and npm ls clean; Leaflet installation audit found no vulnerabilities |

The final Chromium run took 161.75s and recorded zero uncaught JavaScript errors. There
are 66 screenshots including the two new Phase 16 captures. Port 8780 was gracefully
restarted after verification; the page and new Leaflet assets return 200. The existing
workspace's SQLite logical-dump fingerprint matched before/after startup, preserving its
saved records. Temporary browser-test databases were kept separate and shut down.

Phase 16 adds **28 Python, two Node and five browser cases**. Final checks have zero
failures; no test was removed/skipped. The browser suite uses disposable migrated SQLite
databases and fictional data. It exercises real Leaflet click/drag, permission denial and
granted synthetic geolocation, verified pin submission/approval and rider navigation,
chronological completion history, empty/outage recovery, original COD and five viewports.
Only tile images, empty history and outage responses are explicitly injected fixtures.

During development, a fault interceptor was corrected to include paginated event URLs;
an oversized pytest parameter received a short ID to avoid Windows temporary-path errors.
These were harness failures, not invented backend defects. A history status separator was
normalized to plain text. No failed write was replaced with simulated persistence.

Evidence: [browser outcomes](phase16/BROWSER_OBSERVATIONS.json),
[offline AI result](phase16/AI_READINESS.json) and
`visual-testing/screenshots/phase16-*.png`. Reproduce with `npm.cmd run test:browser`.
From backend, `python -m tools.evaluate_ai_readiness` checks labels without inference.

## AI readiness and activation

The Python interface remains the single authoritative boundary. Prepared providers:

- `gemini`: configurable-model REST codec, adapted from preserved TypeScript concepts to
  Python's evidence schema. Its format was reviewed against the [official structured-output
  guide](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en).
- `json_http`: trusted HTTPS service accepting `{model,instruction,input,response_schema}`
  and returning `{output: object|string}`. This normalized contract does not claim native
  compatibility with every vendor.
- `mock` and `disabled`: retained and functioning. The integrated sandbox is still mock-only.

Guards include configurable timeout, no redirects/ambient proxies, bounded response size,
duplicate-key/non-JSON-number rejection, strict Pydantic validation, evidence grounding,
rate-limit/timeout/failure degradation and safe errors without upstream bodies/keys.
Gemini generation is capped at 2048 output tokens and rejects incomplete candidates.
Phone, COD and township remain deterministic; GPS/confidence outputs are forbidden.
Unknown/ambiguous values stay unknown. Invalid/invented suggestions retain deterministic
results. No arbitrary scheduling decisions are accepted from AI.

Later activation, **only after explicit permission and an approved external-call budget**:

1. Select provider/model, review retention and sanitized payloads, and use fictional input.
   Redaction covers recognized phones, labeled names and sensitive spans; it is not universal
   PII recognition. Unlabelled names in address prose remain a privacy-review concern.
2. Configure the normal backend privately with `LANNPYA_PARSER_MODE=hybrid`,
   `LANNPYA_AI_PROVIDER=gemini` or `json_http`, `LANNPYA_AI_MODEL=<approved-model>`,
   `LANNPYA_AI_API_KEY=<server-secret>` and, for generic HTTP, `LANNPYA_AI_ENDPOINT`.
   Keep `LANNPYA_AI_EXTERNAL_REQUESTS_ENABLED=false` while running offline tests.
3. After approval, explicitly enable that flag in the intended backend process and run a
   bounded fictional evaluation. No automatic retries or default real model are supplied.
   Never put provider secrets in browser/Vite configuration or Git.
4. The local BFF intentionally overrides provider selection to mock. Real AI in this UI
   needs a later reviewed server-side configuration/indicator change; setting environment
   variables alone does not activate that sandbox. Its AI MOCK label remains accurate.
5. Set the flag false or choose `disabled` to stop external inference.

## Benchmark and limits

Twelve labeled synthetic Burmese/Myanglish cases cover landmarks, combined floor/unit,
instructions, mixed language, time expressions, ambiguous locations and malicious/invalid
outputs. Tests reject hallucinated optional fields, protected-field overwrites, malformed
JSON, oversized envelopes and incomplete responses. Time expressions are tested separately
with deterministic rules; quoted instructions never automatically reschedule deliveries.

Offline evidence reports **12 valid expected schemas, zero real-model calls and
`model_accuracy: null`**. Fake transport proves wire/error contracts, not extraction quality
or live provider availability. Map interaction, review, persistence and history are real;
the running integrated AI enrichment remains mocked.

Production authentication/tenant authorization, PostgreSQL deployment, secure hosting and
trusted geospatial data remain blockers. Keep this workspace on loopback. Next: approve
and evaluate a provider with a small fictional benchmark, wire reviewed server-side UI
activation, then complete authentication and PostgreSQL before any public demonstration.
