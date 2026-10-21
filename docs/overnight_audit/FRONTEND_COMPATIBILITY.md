# Frontend compatibility status

The root implementation guide describes vanilla JS/Vite/Leaflet and three UI experiences.
Actual frontend source is unavailable; `frontend/` still has only `.gitkeep`. No frontend
file was changed and no Vite/browser/cross-application integration was executed.

The 29-operation API, exact OpenAPI snapshots, Phase 8 compatibility matrix/playbook and new
redacted HTTP samples are ready for the teammate. Private local APIs require a loopback
peer and runtime local actor credential; Vite build variables must never contain tokens.
Separate computers' localhost addresses point to different machines.

Keep live backend, demo simulation and connection error distinct. A pending pin is not an
approved address; buyer Bearer is opaque, not JWT; confidence is GREEN/AMBER/RED, not 99%;
navigation URL requires available accepted coordinates; polling is not WebSockets; COD
collection is an assertion, not remittance. Gate photo, masked calling, routing and real AI
remain absent/simulated. See [integration index](../integration/README.md).

Same-machine synthetic integration may begin immediately after frontend import. Shared
public use still needs production auth, secure hosting and live database validation.
