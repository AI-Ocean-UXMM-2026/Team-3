# MTT live integration and local startup

From this worktree in PowerShell:

```powershell
Set-Location 'C:\Users\ZL_shit_H\Documents\Projects\LannPya-AI-mtt-integration'
npm.cmd start -- --port 8781 --state mtt-local
```

Open `http://127.0.0.1:8781`. The existing launcher builds static assets, selects an
installed worktree Python environment (or prepares the pinned environment), migrates
its isolated SQLite workspace and starts the same-origin frontend/BFF on loopback.
An occupied port fails explicitly; use another port rather than stopping unknown servers.
Ctrl+C shuts down the launcher. Tests use randomly selected loopback ports and temporary DBs.

For a repeatable real HTTP delivery and backend-process restart check:
`npm.cmd run verify:mtt-restart`. It owns a temporary SQLite database, reports only
non-sensitive PASS/FAIL evidence, and never resets the regular workspace.

| Entry point | Data and access |
| --- | --- |
| `/` | MTT Signboard, LIVE_BACKEND, database-backed local development actors |
| `/prototype.html` | DEMO_SIMULATION, device-local domain only; no backend write fallback |
| `/api.html` | Preserved advanced developer API workspace, including rider management/cash tools |

This is a developer BFF, not a public admin website. Local role switching is a developer
convenience backed by server-held identities. Never publish/tunnel this server or embed
its private dev token in browser code. Production configuration rejects startup. Direct
business APIs retain their existing local-only access checks. Other computers cannot
use their own localhost to reach this computer; a shared online demo needs reviewed
authentication, authorization, HTTPS and a deployment/BFF design first.

## Actual request mapping

The 35-operation inventory and complete Pydantic schemas are in [OPENAPI.json](OPENAPI.json).
The existing REST contract is unchanged. The local browser posts a same-origin proxy
envelope, not privileged headers:

```javascript
const {csrf} = await (await fetch('/dashboard/bootstrap')).json();
const response = await fetch('/dashboard/api', {
  method: 'POST', headers: {'Content-Type':'application/json','X-Dashboard-CSRF':csrf},
  body: JSON.stringify({method:'POST',path:'/api/orders/parse',body:{raw_text:
    '09790000000, Hlaing, COD 25000, Fictional gate'},actor:'dispatcher'})
});
if (!response.ok) throw new Error('Backend operation failed; refresh before retrying.');
const {data} = await response.json();
// data.address.phone_number === '09790000000'; data.ai.status === 'mock'.
```

All samples are fictional testing data, not contacts to call. Use `LocalWorkspaceApi`
for full flows; it validates the local origin and keeps native buyer credentials server-side.

| UI operation | Native API |
| --- | --- |
| Read chat / add imported order | POST `/api/orders/parse`; POST `/api/orders` with original `raw_text` and operator-entered `parcel` |
| Manual create | POST `/api/orders` with `structured` and `parcel`; exact COD as a decimal-digit string |
| List / correct / history | GET `/api/orders`; GET/PATCH `/api/orders/{id}`; GET `/api/orders/{id}/events` |
| Generate/revoke link | POST `/api/orders/{id}/confirmation-link` or `/confirmation-link/revoke` |
| Buyer card / verify / private details | GET `/api/confirm/{token}`; POST `/verify` with `last_four`; GET `/details` after verification |
| Buyer pin | PATCH `/api/confirm/{token}/location`: `request_id`, decimal `latitude`/`longitude`, `initial_pin_acknowledged` |
| Availability / reschedule / instructions | PATCH `/api/confirm/{token}/response`: `request_id`, `action`, optional timezone-aware `time_window` and `instructions` |
| Review | GET `/api/orders/{id}/buyer-requests`; PATCH `/buyer-requests/{request-record-id}` with `expected_version`, `decision`, `reason` |
| Route and assignment | POST `/api/routes`; POST `/api/orders/{id}/prepare-assignment`; POST `/api/routes/{id}/actions` with DISPATCH |
| Rider queue / start / deliver / fail | GET `/api/riders/{id}/queue`; PATCH `/api/riders/{id}/deliveries/{order-id}/status` |
| COD/hub closeout | Rider DELIVERED carries explicit `cod_collected` and `actual_amount`; route HANDOVER/RECEIVE_CLOSE record cash custody, not a payment transfer |

## Reviewable demonstration

1. Add a fictional manual order or parse/import a chat with a parcel description/day.
2. Open the saved order and generate a buyer link. Copy/share manually; no messages sent.
3. Open the buyer link, verify the fictional phone's last four digits and select/drag a pin.
4. Optionally request device GPS. Before a click no location permission is requested.
5. Submit acknowledgement, availability/time request and instructions. Review-required
   proposals do not replace canonical coordinates before approval.
6. Return to the order. Review the location AND any separate availability/reschedule
   request explicitly. Location approval does not silently approve time changes.
7. Create a route for the same delivery day, receive the parcel, acknowledge unverified
   map accuracy, assign it and confirm departure. Future-day departures are rejected.
8. Rider refreshes the backend queue, opens navigation if ready, completes delivery
   and explicitly confirms physical COD collection. Refresh/order History shows events.
9. Use hub closeout to record rider handover and physically counted receipt, with any
   discrepancy reason. This does not transfer money electronically.

## Location and confidence policy

- Unknown: no pin. Browsing centre never becomes the submitted delivery point.
- Approximate: no live geocoder is configured; demo centres are never used in live mode.
- Buyer-selected: proposed coordinates, pending review when no trusted reference exists.
- Dispatcher-approved buyer pin: stored with buyer provenance and approval evidence;
  navigation may be ready, but independent geospatial accuracy remains unverified.
- Independently verified: requires a reviewed dataset/reference. None is configured.

The backend alone enforces trusted-reference movement policy using Haversine distance.
It does not promote a submitted or approved pin into the immutable trusted anchor.
Unknown township boundaries require review; no fixture rectangle is used server-side.
GREEN/AMBER/RED come from deterministic backend rules, never a 99% animation.

## Errors, polling and limitations

401 requires re-verification/reconnection; 403 rejects role/CSRF/loopback access;
404 is missing/unavailable data; 409 is stale version, lifecycle or pending review;
422 means invalid fields/ranges/time; 429 requires waiting; 503 means unavailable
service/database. A failed/uncertain write is CONNECTION_ERROR, never simulated success.
Location and availability are two API transactions; a partial failure is explicitly reported.

Rider Refresh performs a new queue GET. Approved changes appear on the next poll/reload;
there are no WebSockets, background tracking or route optimization. Suggested polling
for a future UI is bounded (e.g. 10–15 seconds while visible), respecting rate limits.
External navigation includes coordinates only, never phone/private delivery notes.

Link secrets are returned once and kept in page memory. Reloaded dispatcher pages
cannot recover their plaintext from hashes; “Link secret not loaded” does not mean
no link exists. The original URL still works across a backend restart after verification.
Reissuing a link invalidates the previous one. Avoid sharing screenshots containing links.

Shop prep policy, editing parcel metadata/day, offline replay, retry replanning, chat-share
acknowledgements and product policy editing remain simulation-only/unsupported by the live
contract. They are hidden, read-only or rejected explicitly; no fake save is performed.
The current API applies an approved reschedule time window, not a new parcel route day.
The MTT adapter therefore blocks cross-day APPROVE and retains the request for manual
replanning or rejection. Direct API behavior is unchanged; server-owned cross-day parcel/
route replanning requires a separate product decision and backend extension.
