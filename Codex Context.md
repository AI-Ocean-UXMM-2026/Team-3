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
