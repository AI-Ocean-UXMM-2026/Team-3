# Codex Context

Working checkout: `ZawLwinHtoo/lannpya-ai`, branch `mtt`, cloned at `10daf38`
into `lannpya-mtt`. The sibling `lannpya-ai` checkout was left untouched.

The original static frontend and login/logout used demo state. The old local launcher
uses real FastAPI/SQLite records through a developer bridge, not Supabase.

Implemented Supabase account login/logout, email codes/recovery, password validation,
verified UUID-to-database-role authorization, secure serving/build configuration,
operator provisioning, and database Data API access protection. User requires preserving
the existing UI/UX; no existing CSS or HTML layouts were edited. Secure login reuses
the original sign-in markup and adds necessary security fields in existing form styles.
Email/password was chosen for both dispatcher/rider; database roles route automatically.

Setup and initial audit: [[docs/SUPABASE_AUTH_SETUP]]. Public browser key only;
database and rate-limit secrets stay server-side. Auth templates must contain Token
codes, provider password minimum must be 12, and SMTP needs setup. No real credentials,
remote database, email sender, GitHub secret or deployment was changed. Work is local
and uncommitted; nothing pushed.

Verified: 135 frontend unit tests, six Chrome auth browser flows (desktop/mobile),
10 backend auth cases and 21 API contract/integration tests. Broader backend run had
1038 passes plus two stale contract snapshots, then snapshots were regenerated and
targeted checks passed. Build, Ruff and diff whitespace checks pass. Live PostgreSQL,
actual provider enforcement and Gmail delivery await user configuration.

Latest rider demo request: Gmail replaces phone on enrollment and sign-in. User's
final correction explicitly chooses Gmail/password, not a PIN. Original styling and
layout are preserved; no new CSS. Local demo codes LP-7Q4K, LP-8M2R and LP-3N9T are
visible reusable buttons. They issue documented demo passwords in a clearly labeled
email preview; no Gmail was sent. Accounts are stored only in the demo namespace and
cannot be used for Supabase mode. Existing generated invites still consume through
the domain. The local server permits original inline style attributes for Signboard
motion, while retaining the script policy and local access boundary. Tests: 140
frontend tests and two real local-backend browser tests passed, plus the existing six
Supabase browser flows. See [[docs/SUPABASE_AUTH_SETUP]] for exact demo credentials.

## Automatic rider offers and buyer OTP

The `codex/automatic-rider-otp` task updates the existing dispatcher, buyer and rider
flows without changing their layout or CSS. Buyer verification requests a six-digit OTP;
the local code preview is explicitly simulation-only and protected by the local BFF.
Dispatchers reconfirm after customer updates and reviews, then the server allocates to a
free AVAILABLE rider. Riders must accept before departure; decline requests automatic
replacement. Existing delivery windows, COD, returns and cash closeout remain in the flow.
No real SMS, external credentials or deployment were used. Setup and behavior are in
[[docs/AUTOMATIC_RIDER_OTP]].

## KBH checkout — 2026-10-23
Cloned https://github.com/Ginnxxx/LannPya-kbh.git into `C:\Users\minth\Downloads\Ai ocean\lann pya kbh`. Default branch: `mtt`; fetched HEAD: `5711a2a` (enhance buyer confirmation, rider routing, and map popup modal). Checkout matched `origin/mtt` after clone. No application code changed; earlier notes above describe prior work.


## KBH test results — 2026-10-23
Tested without modifying application code or configured database records. Installed locked npm dependencies; build passed. Frontend: 152 passed, 1 failed (buyer review message versus cutoff state). Backend with dotenv disabled and isolated fixtures: 1094 passed, 6 failed, 1 skipped; failures include stale OpenAPI/schema expectations, cutoff boundary, and local proxy rejecting runtime route. Chrome auth browser tests: 6 passed with mocked accounts; desktop/mobile screenshots inspected. Buyer ETA browser test failed after reload: selected date falls back to today and amendment is rejected by schedule validation. Read-only configured PostgreSQL connection passed; migration 0008_buyer_edit_policy; inspected app tables had zero direct browser-role grants. Auth HTTPS connection refused in this environment, so real login remains unverified. Secure app construction is blocked because order_management_enabled is false. No settings changed. Browser evidence stored outside repository in local temp.

## Dispatcher board deletion — 2026-10-23
Added Delete controls to With rider and Delivered cards (including returned/cancelled cards in that column). Confirmation removes only the dispatcher board card; delivery status, rider work, route history, cash totals and historical records remain intact. Live mode uses the existing admin-only version-checked operations API with REMOVE_FROM_BOARD, storing parcel.dispatcher_deleted_at and an ORDER_CORRECTED audit action. No migration or real database writes were needed. Demo mode uses boardDeletedAt and preserves Undo. Board counts exclude removed cards; other historical views retain them. Updated the three checked-in API documents with the new operation enum.
Verification: 23 backend workflow tests passed, 62 frontend domain/live-store tests passed, four dispatcher deletion UI unit cases passed. Desktop and mobile Chrome checks passed against an isolated local database for With rider and Delivered deletion, cancellation and persistence after reload. Build and changed Python files' Ruff checks passed. The earlier buyer-cutoff frontend failure remains unrelated. No credentials changed. Evidence is in local temp outside the repository.

## First buyer confirmation and delivery-day cutoff — 2026-10-23
User clarified that the first address confirmation is exempt from the edit cutoff. Later changes still close one hour before the selected window on the selected delivery date in Yangon time, with three material edits maximum. New draft orders now support buyer links, OTP and the first submission; initial submissions skip the advance-notice check while past calendar dates and closed/invalid orders remain rejected. A submitted first request after its cutoff is saved, then becomes view-only for later edits. Buyer forms retain the saved delivery day on reload and explain the first-confirmation exemption. Tracking-ID lookup now creates a valid independent portal capability rather than returning an unstored token for an existing link; previously shared links remain valid. Local demo OTP preview also accepts draft orders.
Verification: 159 frontend tests and 116 backend buyer-confirmation tests passed, including fixed-time first-submission cases, previous-day late edits and exact one-hour delivery-day closure. The fresh-draft mobile browser confirmation and future-date/reload/three-edit browser flows passed against isolated data. Build passed; added Python lines introduce no Ruff findings (pre-existing file lint findings remain). Updated [[docs/BUYER_EDIT_CUTOFF_AND_REMINDERS]]. Restarted the local secure server on 127.0.0.1:8782 to load the fix. No role grants, credentials or production order edits were performed.

## Native buyer authorization lifecycle — 2026-10-23
Reproduced valid fresh buyer authorization being cleared when opening another delivery while the store retained verified form details. Browser-held clients now remain separate per delivery token, and asynchronous buyer operations capture the correct client. Duplicate portal submissions are guarded. A genuine authorization expiry clears the verified view and returns to verification while retaining the address draft. Backend authorization checks remain enforced. The earlier expiry-only explanation did not account for valid sessions.
Verification: 161 frontend tests, four native buyer browser cases and six existing auth browser cases passed. An additional Chrome test against the real secure API with disposable SQLite orders passed: two first submissions and an edit after switching back. Build passed; the running 127.0.0.1:8782 site serves the corrected module. No production order changes or role grants were performed.

## Hub account order isolation — 2026-10-23
Each Admin/Dispatcher login now owns an independent workspace; no shared hub membership model exists. Previously all dispatcher/admin order and route queries were global. Shared workspace_scope uses merchant ownership plus the immutable ORDER_CREATED actor so existing and delegated merchant orders retain their proper creator. Scoped reads/counts/search and direct mutation/history/confirmation APIs enforce ownership. Rider queues retain assigned rider access while filtering other hub accounts. New routes record their creating hub; legacy routes infer ownership only when every parcel belongs to one account, persisting that owner during locked hub mutations so empty routes remain reusable. Saved route plans containing foreign orders are withheld and cannot commit; background allocation retries revalidate the recorded dispatcher against order ownership.
Verification: reproduced cross-account lists and direct access with isolated authenticated API tests before fixing. Chrome sign-in/sign-out switching A/B/A and reload passed against the real secure API with disposable SQLite records. The existing order/rider/buyer/auth/workflow regression run had 347 passes and one pre-existing schema table-list expectation failure; later routing/allocation/workflow checks had 77 passes. Isolation regression cases cover search, histories, direct edits/deletion, assignment, legacy routes, saved previews and background retries. Read-only configured database audit found 8 orders from 2 creators and 2 routes with no mixed creators. Restarted 127.0.0.1:8782; health 200. No records were reassigned or deleted, and no credentials or role grants changed.

## Rider acceptance starts delivery — 2026-10-23
User removed the dispatcher departure step after automatic rider acceptance. RiderService.offer_response now changes the accepted order to OUT_FOR_DELIVERY and its owned route to dispatched in the same transaction, preserving offer version checks, authorization checks, audit, idempotent receipts and queue updates. Prototype acceptance mirrors this. The main app removes Send rider out and its click handler, replaces departure instructions with automatic-start copy, and keeps Rider routes with delivery progress and Refresh progress. Rider delivery, cash handover and dispatcher receive/close remain intact. No new services, dependencies or migration.
Verification: 17 automatic-assignment tests passed, including acceptance through delivery, handover and dispatcher close-out; 85 account isolation/workflow/rider tests and 161 frontend tests passed. Build and service Ruff check passed. The older MTT browser journey stops at its buyer-link/OTP fixture before reaching acceptance; it does not provide browser validation for this change. API and rendered UI unit cases cover the changed flow. Configured database had no accepted automatic assignment waiting for departure, so no existing records needed migration. Restarted local secure app on 127.0.0.1:8782.

## Upstream KBH updates merged — 2026-10-23
Fetched origin/mtt and fast-forwarded from 5711a2a to d53d6d2 (six commits): automatic verified-user provisioning, judge demo access, auth layout/labels and rider signup tabs, missing RiderProfile creation, precise rider route matching, and automatic map tiles. Preserved all local fixes using a retained recoverable stash f18051ac2f16a5d94db69abbf6ab1018ab80a69e. Resolved two stash-application conflicts by retaining local buyer cutoff behavior/tests and upstream removal of manual tile loading. Local work remains uncommitted and unstaged; no push. Ignored backend/.env was untouched.
Fixed an upstream integration gap: auth-screen selected a signup role but auth.mjs discarded it. Signup now sends Rider or Dispatcher only; backend tests verify RiderProfile creation and reject public Admin escalation. Updated isolated test auth stubs for verify_user's new request argument. Read-only database checks confirmed both judge auth accounts already exist and are verified, with correct app roles and a judge rider profile. No demo provisioning/password reset scripts were run. Automatic provisioning is enabled in the current configuration.
Verification: build, 162 frontend tests, 46 distinct backend auth/isolation/automatic-assignment tests and eight Chrome browser cases passed. Browser coverage includes sign-in/recovery, account switching/reload, automatic street-tile loading and new buyer submissions against the real isolated API. Restarted 127.0.0.1:8782 with the merged code.

## Rider map controls and optional review reasons — 2026-10-23
Applied Impeccable refinement using existing PRODUCT.md/DESIGN.md; its launcher could not install its engine in the restricted cache, so followed the documented fallback. Fixed map SVG inheritance stretching the Expand/locate icons. Controls now use fixed 20px SVGs, 48px touch targets, clear Expand/Locate me labels, visible focus, and wrapping beside the stop label on narrow screens. GPS and map popup interactions are preserved.
Buyer pin and instruction review reasons are now optional for approval and rejection, in both main-app dialogs and the API schema. Blank text normalizes to null; supplied notes still enforce 500 characters and reject NUL. Actor, decision, version checks and audit remain intact. Prototype pin approval permits blank reasons too; independent manual location verification still requires evidence. Updated all three API schema snapshots.
Verification: 162 frontend tests and 14 focused backend review cases passed (pin/instructions, approve/reject, omitted/blank/short notes, replay/scope/version checks). Chrome verified map controls at 390px and 1280px, GPS/expand/close interactions, and saving an empty-reason review in the rendered prototype. Inspected screenshots in local temp; map imagery is blocked in the isolated visual harness. Build, buyer-schema Ruff and whitespace checks passed. Restarted local secure app on 127.0.0.1:8782.

## Shared rider GPS and buyer road route — 2026-10-23
Implemented a shared assignment-scoped tracking snapshot with current GPS and cached OSRM driving-road geometry. Active accepted riders publish GPS while their delivery page is open; buyer map reads the same snapshot every 15 seconds with buyer authorization. Stops publishing on view cleanup. No interpolated rider location or straight-line road substitute in live maps. Separate delivery_positions storage avoids order/route version changes; migration 0009 applied to configured database, with RLS and browser-role grants denied. Route cache expires from calculation time/origin, stale GPS labelled after 90 seconds and withheld after ten minutes; completion/auth failure clears marker and route. Destination amendments and expanded-map marker restoration handled. Narrowed schematic SVG CSS to direct children so Leaflet road overlays render visibly. Existing Expand/Locate controls preserved. Updated three OpenAPI snapshots.
Verification: 162 frontend tests passed; 10 focused tracking backend tests passed, plus 33 automatic-assignment/isolation regressions passed. Five Chrome map/review browser cases passed at 390px/1280px; inspected mobile screenshot and road geometry. Synthetic GPS covers publishing; real device GPS requires permission and an open rider page. Public OSRM routing is best effort and excludes live traffic. Impeccable fallback retained from prior task. Built frontend and restarted local secure server at 127.0.0.1:8782.
