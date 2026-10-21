# Final local architecture

```text
Browser: frontend/index.html (styled ZLH UI)
  -> local-api.mjs, same-origin cookie + CSRF
  -> guarded local BFF (127.0.0.1 only)
  -> existing FastAPI app factory and server-bound role clients
  -> SQLAlchemy orders/buyers/riders/events + WorkflowRoute
  -> isolated persistent SQLite integration workspace
```

The internal API hop uses ASGI TestClient, not browser mock storage. Existing public
application APIs remain available when running the normal backend independently. The
unified shell exposes allowlisted UI assets and proxy calls, not backend source/data.
Native frontend data mutations use that one authoritative database; a failed live request
never falls through to browser simulation.

Core flow: raw normalization/rules/hybrid boundary -> reviewed persistent order -> native
hashed buyer capability and last-four -> proposed pin/availability -> dispatcher approval
-> physical receipt and atomic route assignment -> departure -> rider delivery/COD ->
counted hub receipt and closeout. Route departure records DELIVERY_STARTED for its stops;
the original per-delivery rider START API remains for legacy non-route orders.

There is one backend/, frontend/, docs/, scripts/, plus preserved order-parser/ research
and tools/. Existing development dashboard and logistics lab remain. Live entry index.html
and browser-only prototype.html are separately labeled. Their service worker never caches
or substitutes live/API/dashboard navigation. The normal project database is untouched.
