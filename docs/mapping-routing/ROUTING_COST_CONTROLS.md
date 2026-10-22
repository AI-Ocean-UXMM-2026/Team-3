# Evaluation usage and cost controls

Default execution permits **zero external calls**. Existing application routing
remains offline with its outbound gate false; the new evaluator is an independent
local CLI, not a browser-accessible paid-routing endpoint.

## Independent gates

Live execution requires all of:

- CLI `--execute-live` plus a deliberate unique `--evaluation-id`.
- Evaluation `live_enabled=true` and native `LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED=true`.
- Local/test environment, correct server credential, and separate TWO_WHEELER
  enablement when requested.
- Enough request, matrix-element and stop budget for the **entire** planned run.
- Complete reviewed pricing for every selected mode, the correct matrix billing
  unit and an estimate within the configured ceiling.
- A new exclusively created writable ledger. Existing/locked/unwritable ledgers
  stop execution before network requests. An exhausted deadline also stops work.

The application provider selection is not rewritten. The evaluation can target
Google while the website continues using its explicitly simulated provider.
Neither key presence nor a dry plan silently enables the outbound gate.

## Configuration

Fields use process environment prefix `LANNPYA_ROUTING_EVAL_`, or the supplied
JSON configuration. Defaults and validation bounds:

| Field | Default | Bound / effect |
|---|---:|---|
| `live_enabled` | false | Independent evaluation opt-in |
| `max_requests` | 0 | 0–32 actual HTTP reservations per evaluation |
| `max_matrix_elements` | 0 | 0–250 cumulative requested elements |
| `max_stops` | 6 | 1–10 deliveries; native stop limit also applies |
| `request_timeout_seconds` | 10 | >0–30; native timeout also caps it |
| `evaluation_timeout_seconds` | 60 | >0–120; shared overall deadline |
| `max_estimated_cost` | 0 | Nonnegative Decimal, maximum 1000 configured currency units |
| `pricing` | null | Mandatory reviewed unit prices for live execution |
| `pricing_max_age_days` | 30 | 1–90; stale price reviews are blocked |

For example, total-timeout environment variable is
`LANNPYA_ROUTING_EVAL_EVALUATION_TIMEOUT_SECONDS`. Safe disabled settings are in
`backend/.env.example`, but the CLI ignores `.env` and accepts process variables
or explicit JSON. JSON values override environment fields. Secrets use the native
server variables and are never accepted in evaluation JSON.

## Explicit price model

No provider rate, free allowance, discount or exchange rate is hardcoded.
`pricing` requires currency, reviewed date, a source reference, and a mode-to-price
map. Each mode requires `route_per_request`, `matrix_unit_price`,
`matrix_billing_unit` (REQUEST/ELEMENT), `route_sku` and `matrix_sku`. Negative,
nonfinite or missing prices are rejected; an incomplete/stale review blocks live
requests. Zero unit prices require an explicitly reviewed configuration too.
Unit tests use clearly labeled invented rates solely to verify arithmetic.

For each mode with six deliveries and seven total locations:

```text
route estimate = 6 × configured route price per request
matrix estimate = 49 × configured matrix price per element
                  OR 1 × configured matrix price per request, when applicable
total estimate = sum of both components over all selected modes
```

Google matrix pricing must use ELEMENT. ORS's billing/quota model must be selected
from the actual approved account/plan; it is not assumed to match Google's.
Amounts use Decimal, avoiding binary floating-point monetary rounding.

[Google's billing documentation](https://developers.google.com/maps/documentation/routes/usage-and-billing)
distinguishes route-query billing from matrix-element billing and identifies
two-wheeler requests as an Enterprise feature. Therefore DRIVE pricing must not be
reused for TWO_WHEELER without checking the applicable SKU. Current numeric rates
and account allowances were not adopted or verified in this task.

## Enforcement and failure behavior

Preflight checks all budgets before creating a ledger or contacting a provider.
The guarded adapter reserves and flushes usage/cost to disk before **every** HTTP
attempt, including matrix chunks. It rechecks caps at that point. Failed requests
still consume reserved budget because billing treatment is provider-dependent.
Reports distinguish reserved requests/cost from HTTP attempts and actual billing.

Transport retries are explicitly zero; redirects and environment proxies are
disabled. There is no retry loop. A rate/quota/credential/system/timeout/malformed
response stops the remaining evaluation. Typed no-route/missing-point cases can
be recorded while continuing within the original cap; they never become fake
successful routes. Provider bodies, API keys and request headers are not logged.

Ledgers live under ignored `.tmp/routing-evaluations/`; no database is used. The
ledger prevents accidental replay of one evaluation ID across processes. It is
not a cumulative organization-wide budget. Another deliberately chosen ID is
another evaluation. Application API usage has separate actor rate limits; these
CLI controls do not cover arbitrary other callers, accounts or API keys.

The configured estimate is **not a billing guarantee or invoice**. Incorrect rates,
currency/SKU choices or other account usage can invalidate it. Owner-controlled
provider quotas, key restrictions and billing monitoring remain necessary before
any real activation. No project, key, paid service or quota was configured here.
