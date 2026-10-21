# ZLHantigravity deep review

Reviewed at commit recorded in SOURCE_REFS.json. Root frontend is vanilla HTML/CSS and ES
modules, not Vite: api.html/api-workspace.mjs is the live native API workspace; index.html
and functional-app/workflow-domain form the separate device-local prototype. Styles preserve
admin overview, customer card, rider current stop, route schematic, delivery timing and cash
handover. The map is explicitly illustrative; no independent geospatial proof exists.

Backend lives at lannpya-ai/backend and descends from the mature API implementation. It adds
workflow_routes and migration 0004, parcel metadata, server-bound /api/session, routes/actions,
order operations and atomic prepare-assignment. Buyer hashed tokens/last-four and rider
scoping remain. 447 backend tests passed. Core APIs extend older main, but lack the newer
local hardening, corpus, reliability tests and dashboard; these were preserved from the overlay.

The native UI uses persistent backend APIs, unlike the prototype's localStorage engine.
Its original private token entry uses memory rather than a hardcoded key, but the integration
requirement is stronger: privileged credentials must stay server-side. The final local BFF
replaces this connection step, preserving styling and business controls. Buyer requests still
require the actual backend challenge/short-lived authorization. No browser admin token is returned.

Root frontend had no build script or Vite dependencies. Syntax checks passed. Seventeen
UI harness cases hit `Cannot use import statement outside a module`: the import-stripping
regex did not accept CRLF after Windows checkout. The integration fixes the harness and
updates its assertions for the new credential boundary; all retained UI cases pass.

Real AI exists only in the sibling TypeScript order-parser adapter, never the Python backend.
It can call Gemini if separately run with a key and otherwise uses explicit offline recordings
and heuristics. No paid/live calls were made. Browser bundle is encoding/rules/dictionary only.
Its approximate places are not imported into the authoritative backend's trusted catalog.
CORS/port improvements are useful historical context but the final app uses one local origin.


## Remote advancement reviewed before completion

ZLHantigravity advanced externally during this task from 172af9690056318e23c8ef02c7f6276da8e3255c
to 3018adffa6eb027785cf0dd983184f92a2be8d1f (three commits). The final delta was fetched and
reviewed: Python formatting/E501 suppression, Windows LF attributes and CRLF-aware test
import stripping, and diagnostics/log capture for its original multi-process launcher.
No new API, schema, AI or UI workflow was introduced. We incorporated its .gitattributes;
our equivalent CRLF fix and stricter lint already apply. We retain our one-origin server-side
credential launcher rather than copying its older actor-token launcher or deletion/checkpoint
utilities. The 447-test source run was at the initial SHA, not falsely attributed to the new
SHA. The final integrated implementation was independently tested. This remote change was
made externally; no teammate branch was pushed or modified by this task.

The latest 3018adf frontend was also executed in a new detached worktree: **93 tests passed**. The late delta does not add new product workflows or AI providers.
