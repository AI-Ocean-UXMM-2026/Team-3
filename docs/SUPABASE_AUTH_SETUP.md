# Supabase authentication setup

This change adds real authentication while retaining the existing Signboard markup,
styles, shop tabs, and dispatcher/rider pages. It is prepared locally on `mtt` from
`10daf38159ff2d9fb11d9d79333723eb6c70e453`; no real project, database, email sender,
GitHub secret, or deployed site was changed during development.

## What the original branch actually connected

| Entry / feature | Data source at the inspected commit |
| --- | --- |
| Static `index.html` and `prototype.html` | Explicit browser demo and localStorage |
| Login / logout in either mode | Device-only flag, fixed password `lannpya`, fixed PIN `1234` |
| `npm start` service board, orders, riders, routes, cash closeout | Real FastAPI calls through local developer bridge, persistent isolated SQLite |
| Buyer confirmation under the local server | Real database link/session/response APIs |
| Supabase / PostgreSQL | SQLAlchemy driver supported, not configured by the local launcher |
| AI / routing | Mock AI and explicitly simulated routing unless separately configured |

Evidence: `frontend/runtime-config.js`, `frontend/demo-config.js`,
`frontend/js/functional-app.js`, `frontend/js/local-api.mjs`,
`frontend/js/live-store.mjs`, `backend/tools/integrated_workspace.py`,
`backend/tools/backend_test_dashboard/runtime.py`, `backend/app/core/dev_access.py`.

## Resulting data and identity flow

The secure entry uses Supabase email/password or email OTP. Supabase owns password
hashes, email verification, refresh tokens, and rate limits. The browser sends the
user's bearer token to FastAPI. For each protected request, FastAPI asks the configured
Supabase `/auth/v1/user` endpoint to validate it and requires a confirmed email.
It looks up the returned UUID in the application `users` table, and uses that row's
role. User-editable metadata and browser role switches never grant permissions.
No account automatically becomes a dispatcher merely by signing up.

Email/password is shared by dispatchers and riders. The account's server role opens
its existing screen. A linked, verified phone/password account can also use the
existing phone/email input; email is still required for verification and recovery.
There is no production four-digit shared PIN. The device demo remains separate.
New password changes require 12–128 characters and confirmation; common passwords
are rejected in the UI. Server enforcement must be configured below as well.

The existing Keep me signed in checkbox controls SDK storage: checked uses
localStorage, unchecked uses sessionStorage. Tokens are never put in URLs or logs.
Logout revokes the current Supabase refresh session and clears local credentials;
Supabase access JWTs can remain valid until expiry. Use a short JWT lifetime.
Email OTP is a recovery/sign-in alternative, not a claim of two-factor authentication.

## Required Supabase account and email settings

1. Enable Email auth and **Confirm email**. Set minimum password length to **12**.
   Enable leaked-password rejection when supported by the project plan. Keep provider
   authentication rate limits enabled. Match the UI maximum of 128 characters in any
   additional clients; a frontend check alone is not a server security control.
2. Configure a verified custom SMTP sender. Gmail is a supported recipient; no Gmail
   API, Gmail password, or access to users' inboxes is needed. Default Supabase mail
   delivery has restrictions and must not be assumed to support arbitrary recipients.
3. Set Site URL and allow-listed redirect URLs to the actual HTTPS app origin.
4. **Mandatory for this code-based UI:** update all three Supabase Auth email templates
   **Confirm signup**, **Magic Link**, and **Reset Password** to show `{{ .Token }}`.
   Example template body:

   ```html
   <h2>Your LannPya verification code</h2>
   <p>Enter this code in LannPya:</p>
   <p><strong>{{ .Token }}</strong></p>
   <p>If you did not request it, ignore this email. Never share the code.</p>
   ```

   Set email OTP length to **6 digits** and expiry to **10 minutes**. The UI accepts
   6–10 digits, limits resends to one per minute, and treats expired codes as errors.
   Supabase's own limits remain authoritative. Default magic-link-only templates will
   **not** work: this app intentionally does not import sessions from URL fragments.
5. Create/verify initial accounts, then provision their database roles as below.
   Disable open signup in Supabase if the deployment should be invitation-only.
   Require CAPTCHA if account abuse warrants it; this UI does not currently mount a
   CAPTCHA widget, so add provider widget integration before turning that setting on.

## GitHub and server configuration

Do not commit credentials. GitHub repository **Settings → Secrets and variables →
Actions** stores build inputs for the manual **Build Supabase frontend** workflow:

| Name | Location | Browser-visible? |
| --- | --- | --- |
| `LANNPYA_SUPABASE_URL` | GitHub Actions variable and backend environment | Yes |
| `LANNPYA_SUPABASE_PUBLISHABLE_KEY` | GitHub Actions secret and backend environment | Yes, by design |
| `LANNPYA_API_BASE_URL` | GitHub Actions variable for separate frontend hosting | Yes |
| `LANNPYA_DATABASE_URL` | Deployment environment secret; never frontend build inputs | No |
| `LANNPYA_BUYER_RATE_LIMIT_SECRET` | Deployment environment secret, random ≥32 characters | No |

Use the project's `sb_publishable_...` key (or legacy **anon** key), never `sb_secret_...`
or `service_role`. Build/server validation rejects private keys in browser config.
No Supabase service-role key is required by this implementation. A GitHub secret does
not automatically become a hosted server environment variable: configure the deployment
to inject the server values. This workflow builds an artifact; it does not deploy it.

On the backend, set:

```dotenv
LANNPYA_ENVIRONMENT=production
LANNPYA_ORDER_MANAGEMENT_ENABLED=true
LANNPYA_SUPABASE_AUTH_ENABLED=true
LANNPYA_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
LANNPYA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_PUBLIC_KEY
LANNPYA_DATABASE_URL=postgresql+psycopg://YOUR_SERVER_CONNECTION_WITH_TLS
LANNPYA_BUYER_RATE_LIMIT_SECRET=YOUR_RANDOM_SERVER_ONLY_VALUE
LANNPYA_BUYER_FRONTEND_BASE_URL=https://YOUR_APP
LANNPYA_CORS_ORIGINS=["https://YOUR_APP"]
```

Use the Supabase connection dialog's SQLAlchemy/psycopg PostgreSQL string with TLS.
The Auth publishable key is not a database password. The secure server refuses the
implicit SQLite default in production. The old `npm start` launcher still deliberately
uses its own local SQLite sandbox and ignores the production database selection.

## Database initialization and role provisioning

Use a fresh staging project first. From `backend`, using the project's installed
Python environment:

```text
python -m alembic upgrade head
```

Then run `backend/scripts/secure_supabase_tables.sql` as the PostgreSQL owner. It
enables RLS and removes public/anon/authenticated access to **only the listed LannPya
application tables**. Clients must use the authorized backend API. Keep the database
owner/bypass-RLS connection server-only. The secure server checks browser grants on
startup and refuses to serve if the Data API could bypass the backend's role checks.
Repeat this step for any new application tables introduced by future migrations.

Copy the verified account UUID from Supabase Auth Users and provision its role:

```text
python -m scripts.provision_auth_user --auth-user-id SUPABASE_UUID --email dispatcher@example.com --name "Dispatcher name" --role Dispatcher
python -m scripts.provision_auth_user --auth-user-id SUPABASE_UUID --email rider@example.com --name "Rider name" --role Rider
```

Use a different actual UUID for each account. The rider command also creates its
operational profile. Existing fictional local riders are not automatically linked to
real users, and this command refuses to overwrite an existing UUID or email. Existing
data requires a deliberate identity-mapping migration rather than relabeling IDs.
Dispatcher accounts manage this installation's shared hub; multi-hub tenant isolation
is not introduced by this change.

## Run the secure app

From repository root:

```text
npm ci
npm run build
```

From `backend`:

```text
python -m uvicorn tools.secure_workspace:application --factory --host 127.0.0.1 --port 8782 --no-access-log
```

Put this server behind an HTTPS reverse proxy on the public deployment. It serves
`frontend/dist` and exposes only public Supabase runtime values. If hosting frontend
separately, build with all three public build variables above and configure exact
backend CORS origins. The default unconfigured main page shows setup status; it never
substitutes demo login. `prototype.html` remains an explicit demonstration.

Buyer confirmation keeps its private link plus phone-last-four verification rather
than requiring a new buyer account. Production buyer endpoints need the rate-limit
secret above. AI, road routing, SMS delivery and map-provider setup are separate from
authentication and are not enabled by an Auth key.

## Rider invitation rehearsal for the live demo

The rider's existing screen now uses **Gmail + Password**, with no PIN boxes. Its
first-time form has an invitation code and Gmail, in the original layout and styles.
Use the local `npm start` workspace for database-backed demonstrations, or the
explicit browser prototype. These reusable codes are shown as buttons on the rider
first-time form:

| Demo invitation | Demo password issued |
| --- | --- |
| `LP-7Q4K` | `LannPyaDemo!1234` |
| `LP-8M2R` | `LannPyaDemo!2468` |
| `LP-3N9T` | `LannPyaDemo!4826` |

Choose a code, enter a Gmail address, and continue. The sign-in form shows a clearly
labeled **demo email preview**, then accepts that Gmail/password combination. No email
is sent. Wrong passwords, unregistered Gmail addresses and unknown invitations are
rejected. Rehearsal registrations persist on the same browser and origin. A ready-made
login is `rider.demo@gmail.com` / `LannPyaDemo!1234`.

The codes can be reused for rehearsals and map to the available local rider; they do
not create Supabase accounts or grant production access. Existing hub-generated
one-use invitations still follow their original expiry and consumption rules. Actual
Gmail delivery continues to require the configured SMTP/Supabase setup above. The
production entry retains real Supabase email/password authentication.

## Verification and limits

Local tests cover provider token rejection, verified identity mapping, missing
accounts, rider/dispatcher separation, and private-key rejection. Browser tests use
intercepted Supabase responses to exercise password login/logout, successful and
expired email codes, password recovery, confirmation mismatch, and mobile rendering.
The existing frontend suite and static asset build are also checked.

No real Supabase credentials were provided, so hosted PostgreSQL migrations and grant
checks, SMTP/Gmail delivery, actual provider password enforcement, provider limits,
and a real end-to-end session remain unverified until setup. In particular, the email
code tests prove application behavior, not that an actual email has been delivered.

Primary references: [password auth](https://supabase.com/docs/guides/auth/passwords),
[email OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless),
[password security](https://supabase.com/docs/guides/auth/password-security),
[server user validation](https://supabase.com/docs/reference/javascript/auth-getuser),
[sign-out semantics](https://supabase.com/docs/guides/auth/signout).
