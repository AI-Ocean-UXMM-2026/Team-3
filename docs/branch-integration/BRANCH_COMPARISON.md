# Source comparison

| Source | Actual implementation | Reuse and risks |
| --- | --- | --- |
| main + preserved local overlay | FastAPI, SQLAlchemy/Alembic, rules/hybrid interface, secure buyer verification, orders/riders/events, hardened parser, tests, local dashboard and logistics lab. Product frontend is empty. Local overlay: 812 tests passed independently. | Authoritative foundation; retain every test/tool. Production auth and PostgreSQL remain unverified. |
| checkpoint/admin-rider-workflow | Combined vanilla-JS admin/customer/rider workspace, browser-only prototype, native workflow-route/cash table and migration 0004; backend nested under lannpya-ai. No TypeScript AI package. | Route/cash extensions originate here. Frontend tests encountered CRLF-sensitive import stripping; no incompatible older backend wholesale replacement. |
| mtt | Checkpoint plus order-parser TypeScript package, Gemini REST adapter, recorded/heuristic fallbacks, encoding/dictionary/rules and browser bundle. | 141 parser tests and typecheck passed in isolated worktree. Adapter network calls mocked; no real model accuracy established. Approximate geodata is unsuitable for trusted production triage. |
| ZLHantigravity | mtt plus multi-port CORS/client trimming/rider-port adjustments and Python-path/OpenAPI wording portability changes. Same styled native workspace and workflow backend. | Backend 447 tests passed; frontend syntax passed, UI test harness failed on Windows CRLF. Select frontend/workflow additions; replace browser private-token connection with a local session/CSRF proxy. |

All four trees and histories were inspected, not merely ordered by commit date. ZLH differs
from mtt in five files: UI base selection, launcher CORS, client token trimming, pytest path
and a Python-version-dependent error phrase. Backend schema/service additions are shared.
The checkpoint frontend suite also showed the import-stripping portability defect. We did
not execute an identical second backend suite for checkpoint/mtt where source is shared;
the isolated ZLH backend run and final integration regression cover selected shared logic.

Source strengths retained: mature backend contracts/security; ZLH styling and real API
controls; route/physical-receipt/cash closeout; prototype presentation and offline parser.
Omitted from runtime: nested backend copies, privileged browser-token workflow, direct
checkpoint deletion utility, duplicate static backend host and TypeScript serverless API.
These remain in detached source worktrees and provenance references, not silently discarded.
No actual product frontend source beyond these branches was assumed available.


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
