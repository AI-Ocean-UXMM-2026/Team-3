# AI reconciliation

The selected runtime remains Python deterministic extraction + provider-independent mock
(or disabled) enrichment. Rules extract phone/COD and controlled townships; validated
fields are protected from model overwrite. External providers remain blocked by the gateway.
No key, provider selection or model activation was silently inferred from the environment.

mtt/ZLH contain an actual Gemini REST adapter with configurable model, schema-shaped JSON,
timeout/abort, server-side key header and typed failures, alongside recording and heuristic
fallbacks. Its 141 tests and typecheck passed offline. Requests in adapter tests use fake
transports. This is not evidence of current provider access, Burmese model quality or cost.
The real adapter remains preserved in order-parser/src/ai/, not called by the local app.

We did not splice that standalone serverless pipeline into the Python API: its output
names/provenance differ, it falls through recordings/heuristics and its approximate place
catalog can influence its own triage. Those cannot become authoritative Python GPS/trust.
Only its deterministic browser bundle is retained for the clearly labeled standalone demo.
Future activation needs a Python adapter mapping only evidence-backed optional fields to
AIExtractionResponse, configured model/key, privacy review and explicit permission for
external calls. No provider SDK or paid call was added.

The newly found PRD recommends Gemini Flash, but the user's latest instruction leaves the
provider undecided; that takes precedence. All live UI labels say AI MOCK. Corpus/recording
success and synthetic GREEN candidates are never presented as measured model accuracy.
