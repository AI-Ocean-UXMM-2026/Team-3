# Network, console and security observations

Final instrumented browser pages observed **955 HTTP responses**:

| Status | Count | Interpretation |
| --- | --- | --- |
| 200 | 913 | Successful pages/assets/reads/updates |
| 201 | 31 | Successful resource creation |
| 401 | 1 | Expired buyer authorization |
| 403 | 3 | Wrong buyer digits |
| 404 | 2 | Invalid/revoked buyer capabilities |
| 410 | 1 | Expired link |
| 422 | 3 | Invalid coordinates, unexplained cash difference, past route date |
| 423 | 1 | Locked buyer link |

There were **zero uncaught JavaScript errors**, zero unexpected console errors, zero
unexpected failed requests and zero HTTP 5xx responses. Chromium emitted 12 expected
resource-error console entries: 11 deliberately rejected HTTP requests plus one deliberate
order-write network abort. These are negative-test evidence, not hidden application bugs.
Read-only API inspections and separate anonymous-context security requests are additional
to this instrumented-page response count.

One genuine initial CSP error came from the prototype's external Google font stylesheet.
The blocked links were removed; the existing local font fallback works. CSP remains
first-party only. No new third-party network permission was added. The final prototype
regression and full browser run passed.

Browser request listeners reject any `X-Dev-Access-Token` or Authorization header. Local
privileged credentials and buyer Bearer credentials remain server-side. The browser uses
an HttpOnly, SameSite=Strict local session and CSRF protection. Generated buyer capability
links intentionally contain a token, are treated as private and are masked in captures.
Source-map/private-file checks found no exposed secret assets; static checks found no
literal provider/GitHub keys in the loaded integration modules. This is a targeted check,
not a complete secret-history scan or penetration test.

Anonymous private API access, forged CSRF, invalid/expired/revoked links and lockout were
rejected. The local root deliberately provisions a developer session for a trusted loopback
visitor: it is **not production login**, and must not be publicly exposed or tunneled.
Production fail-closed tests remain passing. Real CORS/LAN hosting was not enabled; the
live UI uses the existing same-origin loopback BFF.

Node's NO_COLOR/FORCE_COLOR warning comes from the test runner environment, not the site.
Machine-readable sanitized evidence is in `BROWSER_OBSERVATIONS.json`.
