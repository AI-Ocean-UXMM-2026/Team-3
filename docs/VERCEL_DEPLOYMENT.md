# Judge deployment

Live site: https://lannpya-ai.vercel.app

If the site, sign-in, or database connection does not work on your network, try a VPN and refresh. Judges can use the sign-in page's **Fill Demo Credentials** button and add sample orders and buyer details to test the connected database.

When a buyer verification-code screen appears, use **123456** or the displayed generated test code for this judge demo. Customer links shared by dispatchers first ask for the order ID and matching buyer phone number, then open the delivery edit page.

Vercel project: `lannpya-ai` in `minthanttunmmgmailcoms-projects`.
The frontend and FastAPI backend deploy together through Vercel Services (beta).
The home page is `/home.html`; the workspace is `/index.html`.

The API service uses persistent Supabase PostgreSQL and Supabase Auth. The browser
receives only the project URL and publishable key from `/runtime-config.js`.
Database credentials remain server-side. Local `.env` files are excluded from
uploads and Git. Migration `0009_delivery_positions` is already applied.

Required project variables, configured for Production and Preview:

- `LANNPYA_DATABASE_URL` (Secret)
- `LANNPYA_SUPABASE_URL` (Config)
- `LANNPYA_SUPABASE_PUBLISHABLE_KEY` (Config)
- `LANNPYA_SUPABASE_AUTH_ENABLED=true`
- `LANNPYA_ORDER_MANAGEMENT_ENABLED=true`
- `LANNPYA_AUTO_PROVISION_USERS=true`
- `LANNPYA_BUYER_RATE_LIMIT_SECRET` (Secret)
- `LANNPYA_ENVIRONMENT=local` and `LANNPYA_BUYER_OTP_MODE=demo`

This is a judge demonstration with real authentication and database persistence.
Buyer SMS uses the existing demo OTP mode; it does not send real SMS. A future implementation phase can add real SMS delivery using the Twilio settings enforced by `Settings`. Serverless
instances can suspend background timers; continuous reminder/recovery processing
requires a separate durable worker or scheduler.

The sign-in screen provides existing judge demo credentials and autofill buttons.
Supabase user access and API role checks remain required. The production domain is
public using Vercel's existing protection settings; deployment protection was not
disabled.

Build frontend with `LANNPYA_RUNTIME_CONFIG=server npm run build` on Vercel. Runtime
configuration is supplied by the API service. Python 3.12 and the PostgreSQL driver
are declared in the backend. Deployments currently use the authenticated Vercel
CLI; automatic Git deployments have not been configured.

Verify after deployment: home page and workspace return 200, `/health` returns
200, judge dispatcher `/api/orders` and rider `/api/riders/{id}/queue` return 200
with their own Supabase access tokens, and anonymous order access returns 401.
Never record access tokens or database URLs in verification output.
