# API contract verification

Actual FastAPI OpenAPI remains **29 operations**, unchanged from Phase 8 snapshots. The full
suite checks equality with `docs/OPENAPI.json` and `docs/integration/OPENAPI.json`, response
model keys, authorization, CORS, pagination/filter boundaries, nulls, enums, errors, UTC
timestamps, Unicode, optimistic versions and buyer/rider idempotency.

No endpoint names, request/response field names, status enums or response schemas changed.
Malformed NUL text now consistently returns the existing 422 validation/error envelope.
`docs/API_CONTRACT.md` documents that input restriction. Ordinary valid input behavior is
preserved. Detector unavailability now returns retained deterministic values with explicit
encoding uncertainty/RED instead of losing the entire parse to an exception.

Order create remains non-idempotent. Buyer/rider writes use a request UUID and exact-body
replay; don't mint a new UUID when retrying an uncertain network result. Coordinate strings,
unknown/null COD, buyer pending review and confidence category meanings remain unchanged.

Shareable redacted response fixtures are in [frontend_samples.json](frontend_samples.json).
These come from real local HTTP responses with synthetic data, not actual frontend calls.
