# Phase 1 scope and design decisions

## Discovery

Inspected `Projects` and recursively inspected `Projects/LannPya-AI`, including hidden
files. The project contained empty `backend` and `docs` directories. No existing source,
frontend, repository configuration, or applicable AGENTS.md was found.

Unavailable: `LannPya_AI_PRD_v2.docx`, other PRD documents, Information Architecture,
and use-case diagram. No unavailable document was read or used. The user's Phase 1
master prompt is the specification. Git was initialized at `LannPya-AI`; no commit,
remote push, or deployment was performed.

## Decisions and assumptions

- API structure is independent of frontend frameworks. Pydantic schemas generate OpenAPI.
- Mock returns null fields for every input, instead of inventing a customer or location.
  Input is not echoed or persisted. No coordinates or numeric confidence are returned.
- `RED` is a deterministic mock safety classification, not an evaluation of the submitted
  address. Reasons explain mock verification status and missing phone/township fields.
  `GREEN` and `AMBER` are reserved enum values; dispatch thresholds are not implemented.
  Actual address normalization and a validated classification rule set are later work.
- COD is nullable whole MMK, represented as a nonnegative integer; confirm any fractional
  currency requirement before implementing real extraction. Unknown COD stays null, not zero.
- Building/floor/unit is one nullable string. Time window is a nullable free-text string
  until scheduling requirements and timezone handling are defined.
- Requests are whitespace-trimmed, 1–10,000 characters, and reject unknown fields. This
  character limit is an MVP assumption, not a streaming HTTP request-size limit.
- Expected provider failures produce 502; request validation produces 422. Error output
  excludes raw input and exception details. Unexpected failures return generic 500 and
  log exception class only. No customer payload logging is added.
- Provider input is internal and validated. Mock performs no network calls. PII filtering
  for a future external provider must be designed before enabling such a provider.
- Local CORS origins are configurable following the [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/).
- Python 3.14 is the installed interpreter; package metadata supports Python 3.11+.
  Only the installed environment has been verified.

## Scope boundary

No database persistence or production database access, real AI, buyer confirmation
links, authentication, rider APIs, route optimization, WebSockets, GPS tracking,
spatial memory, external courier integrations, or billing. No frontend files changed.
No external accounts, services, or secrets are needed for Phase 1.

Missing product documents do not block this mock foundation. Real validation policy,
buyer verification, data retention, provider selection, and persistence design remain
product/engineering decisions for later phases.
