# Live backend and demo mode state contract

The backend does not define a frontend fallback protocol. The frontend implementation is
not present, so its current behavior cannot be verified. This document defines the minimum
client-side distinction needed to keep mock actions from appearing persisted.

```js
const Mode = Object.freeze({
  LIVE_BACKEND: "LIVE_BACKEND",
  DEMO_SIMULATION: "DEMO_SIMULATION",
  CONNECTION_ERROR: "CONNECTION_ERROR",
});
```

| State | Meaning | UI behavior |
| --- | --- | --- |
| `LIVE_BACKEND` | A request to the selected real endpoint succeeded and its response is being rendered. | Label data as saved only after a successful mutation response. Retain server IDs, versions, status and review decisions. |
| `DEMO_SIMULATION` | User explicitly selected a frontend-only demo; state is in memory and not saved in backend/SQLite. | Persistent visible “Demo simulation — not saved” badge. Use fictitious fixtures; never show production-like success receipts. Reset only the simulated state on explicit reset. |
| `CONNECTION_ERROR` | A live backend request timed out, was rejected, returned non-2xx, failed CORS, or returned unreadable data. | Show failed action and retry/back controls. Keep unsaved form input locally. Offer a separate, explicit switch into demo simulation; don't auto-switch the failed operation. |

Suggested state transition:

```text
explicit local/live selection -> LIVE_BACKEND
explicit demo selection       -> DEMO_SIMULATION
live request failure          -> CONNECTION_ERROR
explicit retry                -> LIVE_BACKEND request
explicit “Try demo” choice    -> DEMO_SIMULATION
```

Do not retry non-idempotent mutations with a new identity. Buyer/rider mutation requests
use a client UUID and should reuse the exact same body/UUID when retrying an uncertain
network result. Order create has no idempotency key: after a timeout the client must first
query/reconcile with the dispatcher rather than blindly create another order. The error
may have occurred after the client lost the success response.

`GET /health` only proves an HTTP liveness response. It does not prove management APIs are
enabled, the correct actor is configured, the DB is healthy, or a write will persist. Use
actual workflow responses to determine integration state. A successful parse is stateless;
only `POST /api/orders` 201 creates a record. A buyer `REVIEW_REQUIRED` response means a
request was recorded for review, not that address/queue state changed.

Never merge simulated records into the live order list, assign fake IDs to saved backend
records, or label demo actions as delivered/paid in live mode. Distinguish cached live data
from demo fixtures if offline browsing is later added. No code in the current backend
implements this client state machine.
